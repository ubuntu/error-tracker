import errno
import logging
import os
import re
import shutil

from daisy import metrics, submit, submit_core, utils
from daisy.version import version_info
from daisy.version_middleware import VersionMiddleware

_session = None
path_filter = re.compile(r"[^a-zA-Z0-9-_]")
logger = logging.getLogger("gunicorn.error")


def ok_response(start_response, data=""):
    if data:
        start_response("200 OK", [("Content-type", "text/plain")])
    else:
        start_response("200 OK", [])
    return [data]


def bad_request_response(start_response, text=""):
    start_response("400 Bad Request", [])
    return [text]


def handle_core_dump(_session, environ, fileobj, components, content_type):
    operation = ""
    if len(components) >= 4:
        # We also accept a system_hash parameter on the end of the URL, but do
        # not actually do anything with it.
        uuid, operation, arch = components[1:4]
    else:
        return (False, "Invalid parameters")

    if not operation or operation != "submit-core":
        # Unknown operation.
        return (False, "Unknown operation")
    if content_type != "application/octet-stream":
        # No data POSTed.
        # 'Incorrect Content-Type.'
        return (False, "Incorrect Content-Type")

    uuid = path_filter.sub("", uuid)
    arch = path_filter.sub("", arch)

    return submit_core.submit(_session, environ, fileobj, uuid, arch)


def app(environ, start_response):
    # clean up core files in directories for which there is no pid
    # this might be better done by worker_abort (need newer gunicorn)
    for d in os.listdir("/tmp/"):
        if "cores-" not in d:
            continue
        pid = int(d.split("-")[1])
        try:
            os.kill(pid, 0)
        except OSError as error:
            # that e-t-daisy-app process is no longer running
            if error.errno == errno.ESRCH:
                shutil.rmtree("/tmp/cores-%s" % pid, ignore_errors=True)
                continue
        # there is process running with this pid but its not e-t-daisy-app
        with open("/proc/%s/cmdline" % pid, "r") as cmdline:
            if "e-t-daisy-app" not in cmdline:
                continue
            shutil.rmtree("/tmp/cores-%s" % pid, ignore_errors=True)

    global _session
    if not _session:
        logger.info("running daisy revision: %s" % version_info["revno"])
        _session = metrics.cassandra_session()

    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    if method == "GET" and path == "/nagios-check":
        return ok_response(start_response)
    if path == "/oops-please":
        if environ.get("REMOTE_ADDR") == "127.0.0.1":
            raise Exception("User requested OOPS.")
        else:
            return bad_request_response(start_response, "Not allowed.")

    components = path.split("/")
    length = len(components)

    # There is only one path component with slashes either side.
    if (length == 2 and not components[0]) or (
        length == 3 and not components[0] and not components[2]
    ):
        # An error report submission.
        if len(components[1]) == 128:
            system_hash = components[1]
        else:
            system_hash = ""
        # We pass a reference to the wsgi environment so we can possibly attach
        # the decoded report to an OOPS report if an exception is raised.
        response = submit.submit(_session, environ, system_hash)
    else:
        # A core dump submission.
        content_type = environ.get("CONTENT_TYPE", "")
        fileobj = environ["wsgi.input"]
        response = handle_core_dump(
            _session, environ, fileobj, components, content_type
        )

    if response[0]:
        return ok_response(start_response, response[1])
    else:
        return bad_request_response(start_response, response[1])


try:
    import django

    # use a version check so this'll still work with precise
    if django.get_version() == "1.8.7":
        from django.conf import settings

        settings.configure()
        django.setup()
except ImportError:
    pass

metrics.record_revno()
application = utils.wrap_in_oops_wsgi(VersionMiddleware(app))
