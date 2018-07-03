from rest_framework import viewsets
from job_manager.api.serializers import JobSerializer
from job_manager.models import Job, Task
from job_manager.authentication import JobTokenAuthentication
from rest_framework.permissions import IsAuthenticated

class JobViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)

    queryset = Job.objects.all()
    serializer_class = JobSerializer

    # def update(self, request, pk=None):
    #     print(request)
    #
    # def partial_update(self, request, pk=None):
    #     print(request)
