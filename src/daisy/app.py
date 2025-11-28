from flask import Flask, request
from flask.logging import default_handler

from daisy.submit import submit
from daisy.submit_core import submit_core
from errortracker import cassandra, config

cassandra.setup_cassandra()
config.logger.addHandler(default_handler)
app = Flask(__name__)


@app.route("/<system_token>", methods=["POST"])
def handle_submit(system_token):
    return submit(request, system_token)


@app.route("/<oopsid>/submit-core/<architecture>/<system_token>", methods=["POST"])
def handle_submit_core(oopsid, architecture, system_token):
    return submit_core(request, oopsid, architecture, system_token)


def __main__():
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    __main__()
