from flask import Flask, request
from flask.logging import default_handler

from daisy.submit import submit
from daisy.submit_core import submit_core
from errortracker import cassandra, config

config.logger.addHandler(default_handler)


def create_app():
    cassandra.setup_cassandra()
    app = Flask(__name__)

    @app.route("/<system_token>", methods=["POST"])
    def handle_submit(system_token):
        return submit(request, system_token)

    @app.route("/<oopsid>/submit-core/<architecture>/<system_token>", methods=["POST"])
    def handle_submit_core(oopsid, architecture, system_token):
        return submit_core(request, oopsid, architecture, system_token)

    return app


def __main__():
    create_app().run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    __main__()
