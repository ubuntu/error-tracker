from django.contrib.auth.decorators import user_passes_test, login_required

groups = [
    "daisy-pluckers",
    "canonical-ubuntu-platform",
    "canonical-losas",
    "canonical-product-strategy",
    "canonical-hw-cert",
    "canonical-hwe-team",
    "error-tracker-access",
    "online-accounts",
]


def can_see_stacktraces(func):
    in_groups = lambda u: u.groups.filter(name__in=groups).count() > 0
    l = "/login-failed"
    return login_required(user_passes_test(in_groups, login_url=l)(func))
