import binascii
import os
import uuid
from os.path import join

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseNotFound, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import action, api_view

from plantit.runs.models import Run, Status
from plantit.targets.models import Target
from plantit.runs.execute import execute


@api_view(['GET', 'POST'])
@login_required
def runs(request):
    if request.method == 'GET':
        runs = Run.objects.all()
        return JsonResponse([{
            'id': run.identifier,
            'work_dir': run.work_dir,
            'cluster': run.cluster.name,
            'created': run.created,
            'state': run.status.state if run.status is not None else 'Unknown',
            'workflow_owner': run.workflow_owner,
            'workflow_name': run.workflow_name
        } for run in runs], safe=False)

    elif request.method == 'POST':
        user = request.user
        workflow = request.data
        now = timezone.now()
        now_str = now.strftime('%s')
        cluster = Target.objects.get(name=workflow['config']['target']['name'])
        workflow_path = f"{workflow['repository']['owner']['login']}/{workflow['repository']['name']}"
        run = Run.objects.create(
            user=User.objects.get(username=user.username),
            workflow_owner=workflow['repository']['owner']['login'],
            workflow_name=workflow['repository']['name'],
            cluster=cluster,
            created=now,
            work_dir=now_str + "/",
            remote_results_path=now_str + "/",
            identifier=uuid.uuid4(),
            token=binascii.hexlify(os.urandom(20)).decode())

        run.status_set.create(description=f"Workflow '{workflow_path}' run '{run.identifier}' created.",
                              state=Status.CREATED,
                              location='plantit')
        run.save()

        config = {
            'identifier': run.identifier,
            'api_url': os.environ['DJANGO_API_URL'] + f"runs/{run.identifier}/status/",
            'workdir': join(cluster.workdir, now_str),
            'clone': f"https://github.com/{workflow_path}" if workflow['config']['clone'] else None,
            'image': workflow['config']['image'],
            'command': workflow['config']['commands'],
            'params': workflow['config']['params'],
            'executor': cluster.executor.lower()
        }
        if 'input' in workflow['config']:
            config['input'] = workflow['config']['input']
        if 'output' in workflow['config']:
            config['output'] = workflow['config']['output']

        execute.delay({
            'repository': workflow['repository'],
            'config': config
        }, run.identifier, run.token, request.user.profile.cyverse_token) # request.session._session['csrfToken']

        return JsonResponse({
            'id': run.identifier
        })


@api_view(['GET'])
@login_required
def run(request, id):
    try:
        run = Run.objects.get(identifier=id)
    except Run.DoesNotExist:
        return HttpResponseNotFound()

    return JsonResponse({
        'id': run.identifier,
        'work_dir': run.work_dir,
        'cluster': run.cluster.name,
        'created': run.created,
        'state': run.status.state if run.status is not None else 'Unknown',
        'workflow_owner': run.workflow_owner,
        'workflow_name': run.workflow_name
    })


@api_view(['GET', 'POST'])
@login_required
@csrf_exempt
def status(request, id):
    if request.method == 'GET':
        try:
            run = Run.objects.get(identifier=id)
            return JsonResponse([
                {
                    'run_id': id,
                    'state': status.state,
                    'location': status.location,
                    'date': status.date,
                    'description': status.description
                } for status in list(run.status_set.all())], safe=False)
        except Run.DoesNotExist:
            return HttpResponseNotFound()

    elif request.method == 'POST':
        status = request.data
        state = int(status['state'])

        if state == 2:
            state = Status.FAILED
        elif state == 3:
            state = Status.RUNNING
        elif state == 4:
            state = Status.CREATED
        else:
            raise ValueError(f"Invalid value for state '{status['state']}' (expected 2 - 4)")

        try:
            run = Run.objects.get(identifier=id)
        except Run.DoesNotExist:
            return HttpResponseNotFound()

        for chunk in status['description'].split('<br>'):
            for line in chunk.split('\n'):
                if 'old time stamp' in line or 'image path' in line or 'Cache folder' in line or line == '':
                    continue
                run.status_set.create(description=line, state=state, location=run.cluster.name)

        run.save()
        return HttpResponse(status=200)