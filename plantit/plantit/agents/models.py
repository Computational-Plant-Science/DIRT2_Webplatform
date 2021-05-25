from enum import Enum
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy
from django_celery_beat.models import PeriodicTask
from django_enum_choices.fields import EnumChoiceField


class Agent(models.Model):
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    workdir = models.CharField(max_length=250)
    username = models.CharField(max_length=100)
    port = models.PositiveIntegerField(default=22)
    hostname = models.CharField(max_length=250)
    pre_commands = models.TextField(blank=True, null=True, default=None)
    max_time = models.DurationField(blank=False, null=False, default=timedelta(hours=1))
    max_walltime = models.PositiveIntegerField(blank=True, null=True, default=10)
    max_mem = models.IntegerField(blank=True, null=True, default=5)
    max_cores = models.IntegerField(blank=True, null=True, default=1)
    max_processes = models.IntegerField(blank=True, null=True, default=1)
    max_nodes = models.IntegerField(blank=True, null=True, default=1)
    queue = models.CharField(max_length=250, null=True, blank=True)
    project = models.CharField(max_length=250, null=True, blank=True)
    header_skip = models.CharField(max_length=1000, null=True, blank=True)
    gpu = models.BooleanField(null=False, default=False)
    gpu_queue = models.CharField(max_length=250, null=True, blank=True)
    disabled = models.BooleanField(default=False)
    public = models.BooleanField(default=False)
    logo = models.URLField(null=True, blank=True)
    callbacks = models.BooleanField(default=True)
    job_array = models.BooleanField(default=False)  # https://github.com/Computational-Plant-Science/plantit/issues/98
    launcher = models.BooleanField(default=False)   # https://github.com/TACC/launcher

    class Executor(models.TextChoices):
        LOCAL = 'local', gettext_lazy('Local')
        SLURM = 'slurm', gettext_lazy('SLURM')
        PBS = 'pbs', gettext_lazy('PBS')

    executor = models.CharField(
        max_length=10,
        choices=Executor.choices,
        default=Executor.LOCAL)

    def __str__(self):
        return self.name


class AgentRole(Enum):
    own = 'OWN'
    run = 'USE'
    none = 'NONE'


class AgentAccessPolicy(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, null=True, blank=True, on_delete=models.CASCADE)
    role = EnumChoiceField(AgentRole, default=AgentRole.run)


class AgentAccessRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, null=True, blank=True, on_delete=models.CASCADE)
    created = models.DateTimeField(default=timezone.now)
    granted: bool = models.BooleanField(default=False)


class AgentTask(PeriodicTask):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    command = models.CharField(max_length=250, null=False, blank=False)