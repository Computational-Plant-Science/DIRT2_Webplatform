import json
import json
import logging
import os
from urllib.parse import parse_qs
from urllib.parse import urlencode

import jwt
import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from github import Github
from requests.auth import HTTPBasicAuth
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated

from plantit.redis import RedisClient
from plantit.sns import SnsClient, get_sns_subscription_status
from plantit.ssh import SSH, execute_command
from plantit.users.models import Profile
from plantit.users.serializers import UserSerializer
from plantit.utils import list_users, calculate_user_statistics, get_user_cyverse_profile, get_user_github_profile, \
    get_user_private_key_path, get_or_create_user_keypair, get_user_statistics
from plantit.misc import get_csrf_token


class IDPViewSet(viewsets.ViewSet):
    permission_classes = (AllowAny,)

    def get_object(self):
        return self.request.user

    @action(methods=['get'], detail=False)
    def cyverse_login(self, request):
        return redirect('https://kc.cyverse.org/auth/realms/CyVerse/protocol/openid-connect/auth?client_id=' +
                        os.environ.get('CYVERSE_CLIENT_ID') +
                        '&redirect_uri=' +
                        os.environ.get('CYVERSE_REDIRECT_URL') +
                        '&response_type=code')

    @action(methods=['get'], detail=False)
    def cyverse_logout(self, request):
        logout(request)
        return redirect("https://kc.cyverse.org/auth/realms/CyVerse/protocol/openid-connect/logout?redirect_uri=https"
                        "%3A%2F%2Fkc.cyverse.org%2Fauth%2Frealms%2FCyVerse%2Faccount%2F")

    @action(methods=['get'], detail=False)
    def cyverse_handle_temporary_code(self, request):
        session_state = request.GET.get('session_state', None)
        code = request.GET.get('code', None)

        if session_state is None:
            return HttpResponseBadRequest("Missing param: 'session_state'")
        if code is None:
            return HttpResponseBadRequest("Missing param: 'code'")

        response = requests.post("https://kc.cyverse.org/auth/realms/CyVerse/protocol/openid-connect/token", data={
            'grant_type': 'authorization_code',
            'client_id': os.environ.get('CYVERSE_CLIENT_ID'),
            'code': code,
            'redirect_uri': os.environ.get('CYVERSE_REDIRECT_URL')},
                                 auth=HTTPBasicAuth(request.user.username, os.environ.get('CYVERSE_CLIENT_SECRET')))

        if response.status_code == 400:
            return HttpResponse('Unauthorized for KeyCloak token endpoint', status=401)
        elif response.status_code != 200:
            return HttpResponse('Bad response from KeyCloak token endpoint', status=500)

        content = response.json()
        if 'access_token' not in content:
            return HttpResponseBadRequest("Missing param on token response: 'access_token'")
        if 'refresh_token' not in content:
            return HttpResponseBadRequest("Missing param on token response: 'refresh_token'")

        access_token = content['access_token']
        refresh_token = content['refresh_token']
        decoded_access_token = jwt.decode(access_token, options={
            'verify_signature': False,
            'verify_aud': False,
            'verify_iat': False,
            'verify_exp': False,
            'verify_iss': False
        })
        decoded_refresh_token = jwt.decode(refresh_token, options={
            'verify_signature': False,
            'verify_aud': False,
            'verify_iat': False,
            'verify_exp': False,
            'verify_iss': False
        })

        user, _ = User.objects.get_or_create(username=decoded_access_token['preferred_username'])

        user.first_name = decoded_access_token['given_name']
        user.last_name = decoded_access_token['family_name']
        user.email = decoded_access_token['email']
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.cyverse_access_token = access_token
        profile.cyverse_refresh_token = refresh_token
        profile.save()
        user.profile = profile
        user.save()

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(f"/home/")

    @action(methods=['get'], detail=False)
    def github_request_identity(self, request):
        return redirect(settings.GITHUB_AUTH_URI + '?' + urlencode({
            'client_id': settings.GITHUB_KEY,
            'redirect_uri': settings.GITHUB_REDIRECT_URI,
            'state': get_csrf_token(request)}))

    @action(methods=['get'], detail=False)
    def github_handle_temporary_code(self, request):
        state = request.GET.get('state', None)
        error = request.GET.get('error', None)
        if error == 'access_denied':
            return HttpResponseBadRequest()
        if state is None:
            return HttpResponseBadRequest()
        elif state != get_csrf_token(request):
            return HttpResponse('unauthorized', status=401)

        code = request.GET.get('code', None)
        if code is None:
            return HttpResponseBadRequest()

        response = requests.post('https://github.com/login/oauth/access_token', data={
            'client_id': settings.GITHUB_KEY,
            'client_secret': settings.GITHUB_SECRET,
            'redirect_uri': settings.GITHUB_REDIRECT_URI,
            'code': code})

        token = parse_qs(response.text)['access_token'][0]
        user = self.get_object()
        user.profile.github_username = Github(token).get_user().login
        user.profile.github_token = token
        user.profile.save()
        user.save()

        return redirect(f"/home/")


class UsersViewSet(viewsets.ModelViewSet, mixins.RetrieveModelMixin):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)
    logger = logging.getLogger(__name__)

    def get_object(self):
        return self.request.user

    @action(detail=False, methods=['get'])
    def toggle_push_notifications(self, request):
        user = request.user
        sns = SnsClient.get()
        topic_name = f"plantit-push-notifications-{user.username}"

        if user.profile.push_notification_status == 'disabled':
            topic = sns.create_topic(topic_name)
            subscription = sns.subscribe(topic['TopicArn'], 'email', user.email)
            user.profile.push_notification_topic_arn = topic['TopicArn']
            user.profile.push_notification_sub_arn = subscription['SubscriptionArn']
            user.profile.push_notification_status = 'pending'
            user.profile.save()
            user.save()

            return JsonResponse({'push_notifications': user.profile.push_notification_status})
        else:
            sub_status = get_sns_subscription_status(user.profile.push_notification_topic_arn)
            if sub_status == 'pending':
                user.profile.push_notification_status = 'pending'
                user.profile.save()
                user.save()
                return JsonResponse({'push_notifications': sub_status})
            else:
                sns.delete_subscription(user.profile.push_notification_sub_arn)
                sns.delete_topic(user.profile.push_notification_topic_arn)
                user.profile.push_notification_topic_arn = None
                user.profile.push_notification_sub_arn = None
                user.profile.push_notification_status = 'disabled'
                user.profile.save()
                user.save()
                return JsonResponse({'push_notifications': user.profile.push_notification_status})

    @action(detail=False, methods=['get'])
    def toggle_tutorials(self, request):
        user = request.user
        user.profile.tutorials_shown = not user.profile.tutorials_shown
        user.profile.save()
        user.save()
        return JsonResponse({'tutorials': user.profile.tutorials_shown})

    @action(detail=False, methods=['get'])
    def toggle_dark_mode(self, request):
        user = request.user
        user.profile.dark_mode = not user.profile.dark_mode
        user.profile.save()
        user.save()
        return JsonResponse({
            'dark_mode': user.profile.dark_mode
        })

    @action(detail=False, methods=['get'])
    def get_all(self, request):
        users = list_users(request.user.profile.github_token)
        return JsonResponse({'users': users})

    @action(detail=False, methods=['get'])
    def get_current(self, request):
        user = request.user
        stats = get_user_statistics(user)

        if user.profile.push_notification_status == 'pending':
            user.profile.push_notification_status = get_sns_subscription_status(user.profile.push_notification_topic_arn)
            user.profile.save()
            user.save()

        response = {
            'django_profile': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'dark_mode': user.profile.dark_mode,
                'push_notifications': user.profile.push_notification_status,
                'github_token': user.profile.github_token,
                'cyverse_token': user.profile.cyverse_access_token,
                'tutorials': user.profile.tutorials_shown
            },
            'stats': stats
        }

        if request.user.profile.cyverse_access_token != '':
            try:
                response['cyverse_profile'] = get_user_cyverse_profile(request.user)
            except ValueError:
                # if the CyVerse request fails, log the user out
                logout(request)
                return redirect("https://kc.cyverse.org/auth/realms/CyVerse/protocol/openid-connect/logout?redirect_uri=https"
                                "%3A%2F%2Fkc.cyverse.org%2Fauth%2Frealms%2FCyVerse%2Faccount%2F")

        if request.user.profile.github_token != '' and user.profile.github_username != '':
            response['github_profile'] = async_to_sync(get_user_github_profile)(request.user)

        return JsonResponse(response)

    @action(detail=False, methods=['get'])
    def get_by_username(self, request):
        username = request.GET.get('username', None)

        # TODO move to configuration file
        if username == 'Computational-Plant-Science' or username == 'van-der-knaap-lab' or username == 'burkelab':
            if request.user.profile.github_token != '':
                github_response = requests.get(f"https://api.github.com/users/{username}",
                                               headers={'Authorization':
                                                            f"Bearer {request.user.profile.github_token}"})
                return JsonResponse({
                    'django_profile': None,
                    'cyverse_profile': None,
                    'github_profile': github_response.json()
                })
            else:
                return JsonResponse({
                    'django_profile': None,
                    'cyverse_profile': None,
                })

        user = self.queryset.get(owner=username)
        response = {
            'django_profile': {
                'username': username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }

        if request.user.username == user.username:
            response['django_profile']['cyverse_token'] = user.profile.cyverse_access_token

        if request.user.profile.cyverse_access_token != '':
            cyverse_response = requests.get(
                f"https://de.cyverse.org/terrain/secured/user-info?username={user.username}",
                headers={'Authorization': f"Bearer {request.user.profile.cyverse_access_token}"})
            if cyverse_response.status_code == 401:
                response['cyverse_profile'] = 'expired token'
            else:
                cyverse_profile = cyverse_response.json()
                if user.username in cyverse_profile:
                    response['cyverse_profile'] = cyverse_response.json()[user.username]
                    user.first_name = response['cyverse_profile']['first_name']
                    user.last_name = response['cyverse_profile']['last_name']
                    user.save()
                else:
                    print(f"No CyVerse profile")
        if request.user.profile.github_token != '' and user.profile.github_username != '':
            github_response = requests.get(f"https://api.github.com/users/{user.profile.github_username}",
                                           headers={'Authorization':
                                                        f"Bearer {request.user.profile.github_token}"})
            response['github_profile'] = github_response.json()
        return JsonResponse(response)

    @action(detail=False, methods=['get'])
    def get_key(self, request):
        overwrite = request.GET.get('overwrite', False)
        public_key = get_or_create_user_keypair(username=request.user.username, overwrite=overwrite)
        return JsonResponse({'public_key': public_key})

    @action(detail=False, methods=['post'])
    def check_connection(self, request):
        try:
            hostname = request.data['hostname']
            username = request.data['username']
        except:
            return HttpResponseBadRequest()

        if 'password' in request.data:
            ssh = SSH(hostname, port=22, username=username, password=request.data['password'])
        else:
            pkey = str(get_user_private_key_path(request.user.username))
            self.logger.info(pkey)
            ssh = SSH(hostname, port=22, username=username, pkey=pkey)

        with ssh:
            try:
                for line in execute_command(ssh=ssh, precommand=':', command='pwd', directory=None, allow_stderr=False):
                    self.logger.info(line)
                return JsonResponse({'success': True})
            except:
                return JsonResponse({'success': False})

    @action(detail=False, methods=['post'])
    def check_executor(self, request):
        try:
            hostname = request.data['hostname']
            username = request.data['username']
            precommand = request.data['precommand']
            # executor = request.data['executor']
            workdir = request.data['workdir']
        except:
            return HttpResponseBadRequest()

        if 'password' in request.data:
            ssh = SSH(hostname, port=22, username=username, password=request.data['password'])
        else:
            ssh = SSH(hostname, port=22, username=username, pkey=str(get_user_private_key_path(request.user.username)))

        with ssh:
            output = []
            try:
                for line in execute_command(ssh=ssh, precommand=precommand, command='plantit ping', directory=workdir, allow_stderr=False):
                    output.append(line)
                    self.logger.info(line)
                return JsonResponse({
                    'success': True,
                    'output': output
                })
            except:
                return JsonResponse({
                    'success': False,
                    'output': output
                })
