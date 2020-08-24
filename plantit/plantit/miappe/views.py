from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from plantit.miappe.serializers import *


class InvestigationViewSet(viewsets.ModelViewSet):
    queryset = Investigation.objects.all()
    serializer_class = InvestigationSerializer
    permission_classes = (IsAuthenticated,)


class StudyViewSet(viewsets.ModelViewSet):
    queryset = Study.objects.all()
    serializer_class = StudySerializer
    permission_classes = (IsAuthenticated,)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = (IsAuthenticated,)


class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer
    permission_classes = (IsAuthenticated,)


class BiologicalMaterialViewSet(viewsets.ModelViewSet):
    queryset = BiologicalMaterial.objects.all()
    serializer_class = BiologicalMaterialSerializer
    permission_classes = (IsAuthenticated,)


class EnvironmentParameterViewSet(viewsets.ModelViewSet):
    queryset = EnvironmentParameter.objects.all()
    serializer_class = EnvironmentParameterSerializer
    permission_classes = (IsAuthenticated,)


class ExperimentalFactorViewSet(viewsets.ModelViewSet):
    queryset = ExperimentalFactor.objects.all()
    serializer_class = ExperimentalFactorSerializer
    permission_classes = (IsAuthenticated,)


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = (IsAuthenticated,)


class ObservationUnitViewSet(viewsets.ModelViewSet):
    queryset = ObservationUnit.objects.all()
    serializer_class = ObservationUnitSerializer
    permission_classes = (IsAuthenticated,)


class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleSerializer
    permission_classes = (IsAuthenticated,)


class ObservedVariableViewSet(viewsets.ModelViewSet):
    queryset = ObservedVariable.objects.all()
    serializer_class = ObservedVariableSerializer
    permission_classes = (IsAuthenticated,)