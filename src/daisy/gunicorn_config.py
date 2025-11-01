import multiprocessing

workers = 2 * multiprocessing.cpu_count()

bind = "0.0.0.0:8000"

accesslog = "-"
errorlog = "-"
loglevel = "info"
