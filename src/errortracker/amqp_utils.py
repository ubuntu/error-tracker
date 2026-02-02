import socket
from datetime import datetime, timezone

import amqp
from amqp import ConnectionError as AMQPConnectionException

from errortracker import config

logger = config.logger

# From oops-amqp
# These exception types always indicate an AMQP connection error/closure.
# However you should catch amqplib_error_types and post-filter with
# is_amqplib_connection_error.
amqplib_connection_errors = (socket.error, AMQPConnectionException)
# A tuple to reduce duplication in different code paths. Lists the types of
# exceptions legitimately raised by amqplib when the AMQP server goes down.
# Not all exceptions *will* be such errors - use is_amqplib_connection_error to
# do a second-stage filter after catching the exception.
amqplib_error_types = amqplib_connection_errors + (IOError,)

_connection = None


# From oops-amqp
def is_amqplib_ioerror(e):
    """Returns True if e is an amqplib internal exception."""
    # Raised by amqplib rather than socket.error on ssl issues and short reads.
    if type(e) is not IOError:
        return False
    if e.args == ("Socket error",) or e.args == ("Socket closed",):
        return True
    return False


# From oops-amqp
def is_amqplib_connection_error(e):
    """Return True if e was (probably) raised due to a connection issue."""
    return isinstance(e, amqplib_connection_errors) or is_amqplib_ioerror(e)


def get_connection():
    global _connection
    if _connection:
        return _connection
    try:
        if "username" in config.amqp_creds and "password" in config.amqp_creds:
            _connection = amqp.Connection(
                host=config.amqp_creds["host"],
                userid=config.amqp_creds["username"],
                password=config.amqp_creds["password"],
            )
        else:
            _connection = amqp.Connection(host=config.amqp_creds["host"])
        _connection.connect()
        config.logger.info("amqp connected")
        return _connection
    except amqplib_error_types as e:
        if is_amqplib_connection_error(e):
            config.logger.warning("amqp connection issue: %s", e)
            # Reset the connection singleton so that next attempt retries connecting
            _connection = None
            # Could not connect
            return None
        # Unknown error mode : don't hide it.
        raise


def enqueue(message, queue):
    channel = get_connection().channel()
    if not channel:
        return False
    try:
        channel.queue_declare(queue=queue, durable=True, auto_delete=False)
        # We'll use this timestamp to measure how long it takes to process a
        # retrace, from receiving the core file to writing the data back to
        # Cassandra.
        body = amqp.Message(message, timestamp=int(datetime.now(timezone.utc).timestamp()))
        # Persistent
        body.properties["delivery_mode"] = 2
        channel.basic_publish(body, exchange="", routing_key=queue)
        msg = "%s added to %s queue" % (message.split(":")[0], queue)
        logger.info(msg)
        queued = True
    except amqplib_error_types as e:
        if is_amqplib_connection_error(e):
            # Could not connect / interrupted connection
            queued = False
        # Unknown error mode : don't hide it.
        raise
    finally:
        channel.close()
    return queued
