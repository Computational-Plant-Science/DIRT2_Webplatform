from django.db import models

from django.contrib.auth.models import User
from django.db.models import Manager
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from encrypted_model_fields.fields import EncryptedCharField

from plantit.collection.models import Collection

# Create your models here.
from plantit.runs.models.run import Run


class Profile(models.Model):
    """
        Extends the base :class:`django.contrib.auth.models.User` to
        include a user Profile.

        Attributes:
            user (:class:`~django.contrib.auth.models.User`): The user this profile belongs to.
            affiliated_institution (str): The user's institution or company.
            affiliated_institution_type (str): The user's institution type.
            country (str): The user's institution's host country.
            continent(str): The user's institution's continent.
            field_of_study(str): The user's field of study.
            pinned_jobs (ManyToManyField): The user's pinned jobs.
            pinned_collections (ManyToManyField): The user's pinned collections.
    """
    # See https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html#onetoone
    user: User = models.OneToOneField(User, on_delete=models.CASCADE)
    github_username: str = models.CharField(max_length=100, default='', blank=True, null=True)
    github_auth_token = EncryptedCharField(max_length=100, default='', blank=True, null=True)
    country: str = models.CharField(max_length=256, default='', blank=True)
    continent: str = models.CharField(max_length=256, default=None, blank=True, null=True)
    institution: str = models.CharField(max_length=256, default='', blank=True)
    institution_type: str = models.CharField(max_length=256, default='', blank=True)
    field_of_study: str = models.CharField(max_length=256, default='', blank=True)
    pinned_jobs: Manager = models.ManyToManyField(Run, related_name='profile_pins', blank=True)
    pinned_collections: Manager = models.ManyToManyField(Collection, related_name='profile_pins', blank=True)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
        Post-Create hook for django User objects that creates a repective
        profile object for the user.
    """
    if created:
        Profile.objects.create(user=instance)
    else:
        instance.profile.save()


post_save.connect(create_user_profile, sender=User)
