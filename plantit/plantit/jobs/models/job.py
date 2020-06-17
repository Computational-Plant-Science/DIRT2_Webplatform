import json
import os

import binascii

from dagster import DagsterType
from django.conf import settings
from django.db import models
from django.utils import timezone

from plantit.collection.models import Collection
from plantit.jobs.models.abstract_job import AbstractJob
from plantit.jobs.models.cluster import Cluster
from plantit.workflows import registrar


class Job(models.Model, AbstractJob):
    class Meta:
        ordering = ['-created']

    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    created = models.DateTimeField(default=timezone.now())
    token = models.CharField(max_length=40, default=binascii.hexlify(os.urandom(20)).decode())
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submission_id = models.CharField(max_length=100, null=True, blank=True)
    workflow = models.CharField(max_length=280, null=True, blank=True)
    cluster = models.ForeignKey(Cluster,
                                null=True,
                                blank=True,
                                on_delete=models.SET_NULL)
    work_dir = models.CharField(max_length=100,
                                null=True,
                                blank=True,
                                default=timezone.now().strftime('%s') + "/")
    remote_results_path = models.CharField(max_length=100,
                                           null=True,
                                           blank=True,
                                           default=None)
    parameters = models.TextField(blank=True, null=True)

    def __str__(self):
        return "Job: %s, User %s, Workflow: %s, Status: %s, Cluster: %s, Parameters: %s" % (self.pk,
                                                                                            self.user,
                                                                                            self.workflow,
                                                                                            self.current_status().state if self.current_status() is not None else None,
                                                                                            self.cluster,
                                                                                            self.parameters)

    def current_status(self):
        """
            The job's most recent status.

            Returns:
                the most recent status of the job as a :class:`Status` object.
        """
        try:
            return self.status_set.filter(date__isnull=False).latest('date')
        except:
            return None

    def get_params(self):
        """
            Combines workflow and server set parameters into a JSON
            object to be saved provided as the workflow.json file
            to ClusterSide.
            Returns:
                JSON Object containing workflow parameters for this job.
        """

        # self.api_version = params['api_version']
        # self.singularity_url = params['singularity_url']
        # self.token = params['token']
        # self.job_pk = params['job_pk']
        # self.server_url = params['server_url']
        # self.pre_commands = params.get('pre_commands', None)
        # self.singularity_flags = params.get('singularity_flags', [])
        # self.key_order = params.get('key_order', None)
        # self.args = params['parameters']
        params = {
            "server_url": settings.API_URL,
            "job_pk": self.pk,
            "token": self.token,
            "parameters": json.loads(self.parameters),
        }
        params.update(registrar.list[self.workflow]) # workflow-specific parameters

        return json.dumps(params)
