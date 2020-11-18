import os
import re
import traceback
from os.path import join

from datetime import datetime, timedelta

import yaml
from celery.schedules import crontab

from plantit.celery import app
from plantit.runs.models import Run, Status
from plantit.runs.ssh import SSH


def clean_html(raw_html):
    expr = re.compile('<.*?>')
    text = re.sub(expr, '', raw_html)
    return text


def execute_command(run: Run, ssh_client: SSH, pre_command: str, command: str, directory: str):
    cmd = f"{pre_command} && cd {directory} && {command}" if directory else command
    print(f"Executing remote command: '{cmd}'")
    stdin, stdout, stderr = ssh_client.client.exec_command(cmd)
    stdin.close()
    for line in iter(lambda: stdout.readline(2048), ""):
        print(f"Received stdout from remote command: '{clean_html(line)}'")
    for line in iter(lambda: stderr.readline(2048), ""):
        print(f"Received stderr from remote command: '{clean_html(line)}'")

    if stdout.channel.recv_exit_status():
        raise Exception(f"Received non-zero exit status from remote command")
    else:
        print(f"Successfully executed remote command.")


@app.task()
def execute(flow, run_id, plantit_token, cyverse_token):
    run = Run.objects.get(identifier=run_id)

    # if flow has outputs, don't push the definition, hidden files or job scripts
    if 'output' in flow['config']:
        flow['config']['output']['exclude'] = [
            ".nvm",
            "flow.yaml",
            os.environ.get('CELERY_TEMPLATE_LOCAL_RUN_SCRIPT', "template_local_run.sh"),
            os.environ.get('CELERY_TEMPLATE_SLURM_RUN_SCRIPT', "template_slurm_run.sh"),
        ]

    try:
        work_dir = join(run.target.workdir, run.work_dir)
        ssh_client = SSH(run.target.hostname,
                         run.target.port,
                         run.target.username)

        with ssh_client:
            msg = f"Creating working directory ('{work_dir}')"
            print(msg)
            run.status_set.create(description=msg, state=Status.RUNNING, location='PlantIT')
            run.save()

            execute_command(run=run,
                            ssh_client=ssh_client,
                            pre_command=':',
                            command=f"mkdir {work_dir}",
                            directory=run.target.workdir)

            msg = "Uploading configuration"
            print(msg)
            run.status_set.create(description=msg, state=Status.RUNNING, location='PlantIT')
            run.save()

            with ssh_client.client.open_sftp() as sftp:
                sftp.chdir(work_dir)
                with sftp.open('flow.yaml', 'w') as flow_def:
                    if 'resources' not in flow['config']['target']:
                        resources = None
                    else:
                        resources = flow['config']['target']['resources']
                    del flow['config']['target']
                    yaml.dump(flow['config'], flow_def, default_flow_style=False)

                    msg = "Uploading script"
                    print(msg)
                    run.status_set.create(description=msg, state=Status.RUNNING, location='PlantIT')
                    run.save()

                    sandbox = run.target.name == 'Sandbox'
                    template = os.environ.get('CELERY_TEMPLATE_LOCAL_RUN_SCRIPT') if sandbox else os.environ.get(
                        'CELERY_TEMPLATE_SLURM_RUN_SCRIPT')
                    template_name = template.split('/')[-1]
                    with open(template, 'r') as template_script, sftp.open(template_name, 'w') as script:
                        for line in template_script:
                            script.write(line)
                        if not sandbox:
                            script.write("#SBATCH -N 1\n")
                            if 'tasks' in resources:
                                script.write(f"#SBATCH --ntasks={resources['tasks']}\n")
                            if 'cores' in resources:
                                script.write(f"#SBATCH --cpus-per-task={resources['cores']}\n")
                            if 'time' in resources:
                                script.write(f"#SBATCH --time={resources['time']}\n")
                            if 'mem' in resources and run.target.name != 'Stampede2': # Stampede2 has KNL virtual memory and will reject jobs specifying memory resources
                                script.write(f"#SBATCH --mem={resources['mem']}\n")
                            script.write("#SBATCH --mail-type=END,FAIL\n")
                            script.write(f"#SBATCH --mail-user={run.user.email}\n")
                            script.write("#SBATCH --output=PlantIT.%j.out\n")
                            script.write("#SBATCH --error=PlantIT.%j.err\n")
                        script.write(run.target.pre_commands + '\n')
                        script.write(
                            f"plantit flow.yaml --plantit_token '{plantit_token}' --cyverse_token '{cyverse_token}'\n")

            msg = f"{'Running' if sandbox else 'Submitting'} script"
            print(msg)
            run.status_set.create(description=msg, state=Status.RUNNING, location='PlantIT')
            run.save()

            execute_command(run=run,
                            ssh_client=ssh_client,
                            pre_command='; '.join(
                                str(run.target.pre_commands).splitlines()) if run.target.pre_commands else ':',
                            command=f"chmod +x {template_name} && ./{template_name}" if sandbox else f"chmod +x {template_name} && sbatch {template_name}",
                            directory=work_dir)

            if run.status.state != 2 and not sandbox:
                msg = f"'{run.identifier}' submitted"
                run.status_set.create(
                    description=msg,
                    state=Status.COMPLETED if sandbox else Status.RUNNING,
                    location='PlantIT')
            else:
                msg = f"'{run.identifier}' failed"
                print(msg)
                run.status_set.create(
                    description=msg,
                    state=Status.FAILED,
                    location='PlantIT')

            run.save()

    except Exception:
        msg = f"Run failed: {traceback.format_exc()}."
        run.status_set.create(
            description=msg,
            state=Status.FAILED,
            location='PlantIT')
        run.save()


@app.task()
def remove_old_runs():
    epoch = datetime.fromordinal(0)
    threshold = datetime.now() - timedelta(days=30)
    epoch_ts = f"{epoch.year}-{epoch.month}-{epoch.day}"
    threshold_ts = f"{threshold.year}-{threshold.month}-{threshold.day}"
    print(f"Removing runs created before {threshold.strftime('%d/%m/%Y %H:%M:%S')}")
    Run.objects.filter(date__range=[epoch_ts, threshold_ts]).delete()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Executes every morning at 7:30 a.m.
    sender.add_periodic_task(
        crontab(hour=7, minute=30),
        remove_old_runs.s())
