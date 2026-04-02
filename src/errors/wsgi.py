import os

import oops_dictconfig
from oops_wsgi import install_hooks, make_app
from oops_wsgi.django import OOPSWSGIHandler

from daisy import config
from errors import metrics
from errors.version_middleware import VersionMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "errors.settings")
import django
from django.template.loader import render_to_string


def error_renderer(report):
    return str(render_to_string("500.html", report))


django.setup()

cfg = oops_dictconfig.config_from_dict(config.oops_config)
install_hooks(cfg)
cfg.template["reporter"] = "errors"
kwargs = {
    "oops_on_status": ["500"],
    "error_render": error_renderer,
}
metrics.revno()
application = VersionMiddleware(make_app(OOPSWSGIHandler(), cfg, **kwargs))
