from django.conf.urls import include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import re_path

from errors import views

urlpatterns = [
    re_path(r"^$", views.main),
    re_path(r"^bucket/$", views.bucket),
    re_path(r"^bug/(.*)$", views.bug),
    re_path(r"^filter/(.*)$", views.main),
    re_path(r"^login-failed/?$", views.login_failed),
    re_path(r"^logout/", views.logout_view),
    re_path(r"^main$", views.main),
    re_path(r"^ops/instances/", views.instances_count),
    re_path(r"^oops/(.*)$", views.oops),
    re_path(r"problem/(.*)$", views.problem),
    re_path(r"^retracers-average-processing-time/", views.retracers_average_processing_time),
    re_path(r"^retracers-results/", views.retracers_results),
    re_path(r"^status/?$", views.status),
    re_path(r"^user/(.*)$", views.user),
    re_path(r"^api/", include("errors.api.urls")),
    re_path(r"^", include("social_django.urls", namespace="social")),
]

# This will only be useful if DEBUG=True, so basically only for development
urlpatterns += staticfiles_urlpatterns()
