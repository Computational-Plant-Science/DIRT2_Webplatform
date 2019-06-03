from django.conf.urls import url, include
from rest_framework import routers

from .collection.views import CollectionViewSet, SampleViewSet
from .job_manager.views import JobViewSet, download_results
from .auth.views import login_view, logout_view

router = routers.DefaultRouter()
router.register('jobs', JobViewSet)
router.register('collections', CollectionViewSet)
router.register('samples', SampleViewSet)
urlpatterns = [
    url('files/', include("apis.file_manager.urls")),
    url('workflows/', include("apis.workflows.urls")),
    url('auth/login/', login_view),
    url('auth/logout/', logout_view),
    url(r'jobs/(?P<pk>\d+)/download_results/', download_results),
    url('', include(router.urls))
]
