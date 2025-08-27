from flask import Flask, request

from daisy.submit import submit

app = Flask(__name__)


@app.route("/<system_token>", methods=["POST"])
def handle_submit(system_token):
    return submit(request, system_token)


def __main__():
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    __main__()
