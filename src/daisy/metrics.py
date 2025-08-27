METRICS = None


class Metrics:
    """
    No-opPrintingMetrics class making the rest of the code to work before moving
    that to some more modern tech.
    """

    def __init__(self, namespace):
        self.namespace = namespace

    def meter(self, *args, **kwargs):
        print(f"meter: {self.namespace}: {args=} | {kwargs=}")

    def gauge(self, *args, **kwargs):
        print(f"gauge: {self.namespace}: {args=} | {kwargs=}")

    def timing(self, *args, **kwargs):
        print(f"timing: {self.namespace}: {args=} | {kwargs=}")


def get_metrics(namespace="daisy"):
    global METRICS
    if METRICS is None:
        namespace = "whoopsie-daisy." + namespace
        METRICS = Metrics(namespace=namespace)
    return METRICS


def record_revno(namespace="daisy"):
    import socket

    from daisy.version import version_info

    if "revno" in version_info:
        m = "%s.version.daisy" % socket.gethostname()
        get_metrics(namespace).gauge(m, version_info["revno"])
