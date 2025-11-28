from django.conf import settings
from django.conf.urls import include
from django.urls import re_path
from django.conf.urls.static import static
from django.views.static import serve
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
    # url(r"^openid/", include("django_openid_auth.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# If we get a request for static content, handle it. This will happen if Apache
# does not have an alias defined for /static, such as when we're using gunicorn
# instead of Apache.
urlpatterns += [re_path(r"^static/(?P<path>.*)$", serve, {"document_root": "static"})]
