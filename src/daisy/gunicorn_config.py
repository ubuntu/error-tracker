import faulthandler
import multiprocessing
import sys

workers = 2 * multiprocessing.cpu_count()

bind = "0.0.0.0:8000"

accesslog = "-"
errorlog = "-"
loglevel = "info"


def worker_abort(worker):
    """Dump worker stacks on SIGABRT, normally sent after a Gunicorn timeout."""
    worker.log.error("Daisy worker aborted: pid=%s; dumping Python thread stacks", worker.pid)
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
