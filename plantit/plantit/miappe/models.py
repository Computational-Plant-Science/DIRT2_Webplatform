from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy


class Investigation(models.Model):
    class License(models.TextChoices):
        CC_BY = 'BY', gettext_lazy('CC BY 4.0'),
        CC_BY_SA = 'SA', gettext_lazy('CC BY-SA 4.0')
        CC_BY_ND = 'ND', gettext_lazy('CC BY-ND 4.0')
        CC_BY_NC = 'NC', gettext_lazy('CC BY-NC 4.0')
        CC_BY_NC_SA = 'NS', gettext_lazy('CC BY-NC-SA 4.0')
        CC_BY_NC_ND = 'NN', gettext_lazy('CC BY-NC-ND 4.0')

    id = models.CharField(max_length=255, unique=True, blank=True)
    title = models.CharField(max_length=255, blank=False)
    description = models.TextField(blank=True)
    submission_date = models.DateField(blank=True, null=True)
    public_release_date = models.DateField(blank=True, null=True)
    license = models.CharField(max_length=2, choices=License.choices, default=License.CC_BY)
    miappe_version = models.CharField(max_length=50, blank=True)
    associated_publication = models.CharField(max_length=255, blank=True)


class Study(models.Model):
    id = models.CharField(max_length=255, unique=True, blank=True)
    title = models.CharField(max_length=250, blank=False)
    description = models.TextField(blank=True)
    start_date = models.DateField(default=timezone.now, blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    contact_institution = models.CharField(blank=True, null=True)
    country = models.CharField(max_length=2, blank=True, null=True)
    site_name = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(blank=True, null=True)
    longitude = models.DecimalField(blank=True, null=True)
    altitude = models.DecimalField(blank=True, null=True)
    experimental_design_description = models.TextField(blank=True)
    experimental_design_type = models.CharField(max_length=255, blank=True)
    experimental_design_map = models.CharField(max_length=255, blank=True)
    observation_unit_level_hierarchy = models.CharField(max_length=255, blank=True)
    observation_unit_description = models.TextField(blank=True)
    growth_facility_description = models.TextField(blank=True)
    growth_facility_type = models.CharField(max_length=255, blank=True)
    cultural_practices = models.TextField(blank=True)


class Role(models.Model):
    user: User = models.ManyToManyField(User)
    description: str = models.CharField(max_length=255, blank=True)


class File(models.Model):
    path: str = models.CharField(max_length=1000, blank=True)
    description: str = models.TextField(blank=True)
    version: int = models.IntegerField(default=1, blank=True, null=True)
    checksum: str = models.CharField(max_length=32, blank=True)


class BiologicalMaterial(models.Model):
    id = models.CharField(max_length=255, unique=True, blank=True)
    organism = models.CharField(max_length=255, unique=True, blank=True)
    genus = models.CharField(max_length=255, blank=True)
    species = models.CharField(max_length=255, blank=True)
    infraspecific_name = models.TextField(blank=True)
    latitude = models.DecimalField(blank=True, null=True)
    longitude = models.DecimalField(blank=True, null=True)
    altitude = models.DecimalField(blank=True, null=True)
    coordinates_uncertainy = models.DecimalField(blank=True, null=True)
    preprocessing = models.TextField(blank=True)
    source_id = models.CharField(max_length=255, blank=True)
    source_doi = models.CharField(max_length=255, blank=True)
    source_latitude = models.DecimalField(blank=True, null=True)
    source_longitude = models.DecimalField(blank=True, null=True)
    source_altitude = models.DecimalField(blank=True, null=True)
    source_coordinates_uncertainy = models.DecimalField(blank=True, null=True)
    source_description = models.TextField(blank=True)


class EnvironmentParameter(models.Model):
    name = models.TextField(blank=True)
    value = models.TextField(blank=True)


class ExperimentalFactor(models.Model):
    type = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    values = models.TextField(blank=True)


class Event(models.Model):
    type = models.CharField(max_length=255, blank=True)
    accession_number = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.now, blank=True, null=True)


class ObservationUnit(models.Model):
    id = models.CharField(max_length=255, unique=True, blank=True)
    type = models.CharField(max_length=255, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    spatial_distribution = models.TextField(blank=True)
    factor_value = models.TextField(blank=True)


class Sample(models.Model):
    id = models.CharField(max_length=255, unique=True, blank=True)
    structure_development_stage = models.CharField(max_length=255, blank=True)
    anatomical_entity = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    collection_date = models.DateField(default=timezone.now, blank=True, null=True)
    external_id = models.CharField(max_length=255, blank=True)


class ObservedVariable(models.Model):
    id = models.CharField(max_length=255, unique=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    accession_number = models.CharField(max_length=255, blank=True)
    trait = models.CharField(max_length=255, blank=True)
    trait_accession_number = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=255, blank=True)
    method_accession_number = models.CharField(max_length=255, blank=True)
    method_description = models.TextField(blank=True)
    method_reference = models.CharField(max_length=255, blank=True)
    scale = models.CharField(max_length=255, blank=True)
    scale_accession_number = models.CharField(max_length=255, blank=True)
    time_scale = models.CharField(max_length=255, blank=True)