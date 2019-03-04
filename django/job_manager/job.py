from __future__ import absolute_import, unicode_literals
from celery import shared_task

import binascii
import os

from django.db import models
from django.utils import timezone
from django.conf import settings
from model_utils.managers import InheritanceManager

from collection.models import Collection

@shared_task
def __run_task__(task_pk):
    """
        Calls the run command asynchronously on the given task
        regardless of its state.

        Args:
            task_pk: pk of the task to run
    """
    task = Task.objects.get_subclass(pk=task_pk)
    task.run()

@shared_task
def __run_next__(pk):
    """
        Runs next uncompleted job task

        This function is run in a Celery worker to make the job run
        asynchronous with the webserver
    """
    job = Job.objects.get(pk=pk)

    if(job.current_status().state == Status.FAILED):
        return

    queued_tasks = job.task_set.filter(complete = False).order_by('order_pos').select_subclasses()
    if(len(queued_tasks) > 0):
        task = queued_tasks[0]
        task.run()
    else:
        job.status_set.create(state=Status.COMPLETED,
                    date=timezone.now(),
                    description=str("All Tasks Finished"))

@shared_task
def __cancel_job__(pk):
    """
        This function will open an ssh connection to the cluster and
        cancel the passed job

        This function is run in a Celery worker to make the job run
        asynchronous with the webserver
    """
    job = Job.objects.get(pk=pk)

    status = job.current_status().state

    if(status < Status.OK):
        return #Job already done.
    elif(status == Status.CREATED):
        # Job never actucally submitted to a cluster
        job.status_set.create(state=Status.FAILED,
                               date=timezone.now(),
                               description="Job Canceled")
    else:
        cmds = format_cluster_cmds(self.cancel_commands)
        #Connect to server
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(cluster.hostname,
                       cluster.port,
                       cluster.username,
                       cluster.password)

        stdin, stdout, stderr = client.exec_command(cmds)
        errors = stderr.readlines()
        if(errors != []):
            self.status_set.create(state=Status.FAILED,
                        date=timezone.now(),
                        description=str(errors))
        else:
            self.status_set.create(state=Status.FAILED,
                                   date=timezone.now(),
                                   description="Job Canceled")
        client.close()


class Job(models.Model):
    """
        The Job class contains all information related to the computations
        to be performed on the cluster.

        A job consists of one or more job_manager.models.Task. Tasks are run
        asending-serially according to their Task.order_pos number. The tasks
        are run server side, but asynchronously via a celery worker.

        Jobs should be cluster agnostic.

        Attributes:
            date_created (DateTime): Date the job was
                created, defaults to timezone.now() (default=now)
            auth_token (str): A authentication token used by
                job_manager.authentication.JobTokenAuthentication to authenicate
                REST API connections (autogenerated by default)
            user (str): user that created the job
            submission_id (str): UID of the cluster job that is performing the job actions.
            work_dir (str): the directory on the cluster to perform the task in.
                 This path is relative to the clusters work_dir path.
                 (autogenerated by default)
    """
    def generate_work_dir():
        """
            Generate a string to use as the the working directory for a job
        """
        return timezone.now().strftime('%s') + "/"

    def generate_token():
        """
            Generate a valid auth_token
        """
        return binascii.hexlify(os.urandom(20)).decode()

    collection = models.ForeignKey(Collection,on_delete=models.CASCADE)
    date_created = models.DateTimeField(default=timezone.now)
    auth_token = models.CharField(max_length=40,default=generate_token)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    submission_id = models.CharField(max_length=100,null=True,blank=True)
    work_dir = models.CharField(max_length=100,
                                null=True,
                                blank=True,
                                default=generate_work_dir)
    results_file = models.FileField(null=True,blank=True,upload_to="files/results/")
    remote_results_path = models.CharField(max_length=100,
                                null=True,
                                blank=True,
                                default=None)
    # def __str__(self):
    #      return "Status: %s, Cluster: %s" (self.current_status().description,self.cluster)

    def current_status(self):
        """
            Returns the most recent status of the job as a :class:`Status` object.
        """
        return self.status_set.latest('date')

    @staticmethod
    def run_next(pk):
        """
            Submit job async

            Args:
                pk (int): the job pk number

            Returns:
                the :class:`Celery` worker object
        """
        return __run_next__.delay(pk)

    @staticmethod
    def cancel(pk):
        """
            Submit job async

            Args:
                pk (int): the job pk number

            Returns:
                the :class:`Celery` worker object
        """
        return __cancel_job__.delay(pk)

class Task(models.Model):
    """
        A task that can be run by a Job

        Once a job is started by calling Job.run_next(job.pk), the first task
        is automatically run, every task after the first will wait until
        the previous tasks finish() method is called.

        Attributes:
            name (str): Name of the task
            description (str): Information and note related to this task
            job (ForeignKey): The job containing this task
            order_pos (int): The position within the job task queue.
                Tasks are executed sequentially according to their
                order_pos. Behavior for mutiple tasks with the same order_pos
                is undefined.
            complete (bool): The is completed
            last_updated (DateTime): last time the task was updated, typically,
                changed when the task is created or marked as complete.
    """
    objects = InheritanceManager()
    name = models.CharField(max_length=20,blank=False,null=False)
    description = models.TextField(blank=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    order_pos = models.PositiveIntegerField(default=1)
    complete = models.BooleanField(default=False)
    last_updated = models.DateTimeField(default=None,blank=True,null=True)

    def run(self):
        """
            Command called to run the task
        """
        raise NotImplmentedError

    def __str__(self):
        return "%s (%d)"%(self.name,self.pk)

    def finish(self):
        """
            Mark this task complete and initiate the next task in the
                task queue for the job
        """
        self.complete = True
        self.last_updated = timezone.now()
        self.save()
        return Job.run_next(self.job.pk)

class Status(models.Model):
    """
        Job status.

        Arguments:
            job (ForeinKey):
            state (int):
            date (DateTime):
            description (str):
    """
    #Possible states
    COMPLETED  = 1 # Job completed
    FAILED     = 2 # Job failed
    OK         = 3 # Status update, everything is OK
    WARN       = 4 # Status update, warning: recoverable error
    CREATED    = 5 # Job was crated but not yet started

    State = (
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (OK, 'OK'),
        (WARN, 'Warning'),
        (CREATED, 'Created')
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    state = models.PositiveIntegerField(choices=State,default=CREATED)
    date = models.DateTimeField(default=timezone.now,blank=True)
    description = models.CharField(max_length=280)

    def __str__(self):
        return self.State[self.state - 1][1]

class DummyTask(Task):
    """
        A task that does nothing except keep track of its run state

        Attributes:
            ran (bool): set to true when :meth:`run` is called
    """
    ran = models.BooleanField(default=False)

    def run(self):
        self.ran = True
        self.save()
