from django.conf.urls import include
from django.urls import re_path
from tastypie.api import Api

from .resources import (
    AverageCrashesResource,
    AverageInstancesResource,
    BinaryPackageVersionsResource,
    CrashSignaturesForBug,
    CreateBugResource,
    DayOopsResource,
    InstanceCountResource,
    InstanceResource,
    InstancesResource,
    MostCommonProblemsResource,
    PackageVersionIsMostRecent,
    PackageVersionNewBuckets,
    ProblemCountResource,
    RateOfCrashesResource,
    ReleasePackageVersionPockets,
    ReportsStateResource,
    RetraceAverageProcessingTimeResource,
    RetraceResultResource,
    SystemCrashesResource,
    SystemImageVersionsResource,
    VersionsResource,
)

v1_api = Api(api_name="1.0")
v1_api.register(RetraceResultResource())
v1_api.register(RetraceAverageProcessingTimeResource())
v1_api.register(InstanceCountResource())
v1_api.register(ProblemCountResource())
v1_api.register(DayOopsResource())
v1_api.register(MostCommonProblemsResource())
v1_api.register(CreateBugResource())
v1_api.register(BinaryPackageVersionsResource())
v1_api.register(SystemCrashesResource())
v1_api.register(RateOfCrashesResource())
v1_api.register(InstanceResource())
v1_api.register(AverageCrashesResource())
v1_api.register(ReportsStateResource())
v1_api.register(PackageVersionIsMostRecent())
v1_api.register(AverageInstancesResource())
v1_api.register(InstancesResource())
v1_api.register(VersionsResource())
v1_api.register(CrashSignaturesForBug())
v1_api.register(PackageVersionNewBuckets())
v1_api.register(SystemImageVersionsResource())
v1_api.register(ReleasePackageVersionPockets())

urlpatterns = [
    re_path(r"^", include(v1_api.urls)),
]
