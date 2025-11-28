#!/usr/bin/python
from functools import wraps
import time
from daisy import metrics as daisy_metrics


# Taken from U1.
def measure_view(view):
    """A decorator for view functions that measures time with txstatsd.

    use it like this:
    @measure_view
    def view(request, *args):
        code

    it will generate a timing metric (durations and rates) in a path
    that looks like this:
    <environ>.<app_name>.<module_path>.<func_name>.<result_code>
    or
    <environ>.<app_name>.<module_path>.<func_name>.error
    if an exception was raised
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        metrics = daisy_metrics.get_metrics("errors")

        # Views in tastypie do not have unique function names.
        if "resource_name" in kwargs:
            name = kwargs["resource_name"]
        else:
            name = view.__name__

        if len(args) > 2 and hasattr(args[2], "user"):
            user = "users.%s." % str(args[2].user)
        else:
            user = ""

        start_time = time.time()
        try:
            result = view(*args, **kwargs)
        except:
            path = view.__module__ + "." + name + ".error"
            metrics.timing(path, time.time() - start_time)
            if user:
                metrics.timing(user + path, time.time() - start_time)
            raise
        else:
            status_code = getattr(result, "status_code", None)
            if status_code is not None:
                path = view.__module__ + "." + name + "." + str(status_code)
                metrics.timing(path, time.time() - start_time)
                if user:
                    metrics.timing(user + path, time.time() - start_time)
            else:
                path = view.__module__ + "." + name
                metrics.timing(path, time.time() - start_time)
                if user:
                    metrics.timing(user + path, time.time() - start_time)
        return result

    return wrapper


def revno(namespace="errors"):
    from errors.version import version_info
    import socket

    if "revno" in version_info:
        m = "%s.version.errors" % socket.gethostname()
        daisy_metrics.get_metrics(namespace).gauge(m, version_info["revno"])
