from django.conf.urls import include, url

from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

from errors import views

urlpatterns = [
    url(r"^$", views.main),
    url(r"^bucket/$", views.bucket),
    url(r"^bug/(.*)$", views.bug),
    url(r"^filter/(.*)$", views.main),
    url(r"^login-failed/?$", views.login_failed),
    url(r"^logout/", views.logout_view),
    url(r"^main$", views.main),
    url(r"^ops/instances/", views.instances_count),
    url(r"^oops/(.*)$", views.oops),
    url(r"problem/(.*)$", views.problem),
    url(r"^retracers-average-processing-time/", views.retracers_average_processing_time),
    url(r"^retracers-results/", views.retracers_results),
    url(r"^status/?$", views.status),
    url(r"^user/(.*)$", views.user),
    url(r"^api/", include("errors.api.urls")),
    url(r"^openid/", include("django_openid_auth.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# If we get a request for static content, handle it. This will happen if Apache
# does not have an alias defined for /static, such as when we're using gunicorn
# instead of Apache.
urlpatterns += [url(r"^static/(?P<path>.*)$", serve, {"document_root": "static"})]
