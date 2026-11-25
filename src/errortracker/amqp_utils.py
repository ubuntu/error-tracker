import errno
import socket
from datetime import datetime, timezone

import amqp
from amqp import ConnectionError as AMQPConnectionException

from errortracker import config

logger = config.logger

# Catch candidates, then distinguish transport failures from protocol/configuration errors.
amqplib_connection_errors = (OSError, EOFError, AMQPConnectionException)
amqplib_error_types = amqplib_connection_errors

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
    """Identify recoverable transport failures, not authentication/protocol errors."""
    return (
        isinstance(e, (ConnectionError, socket.timeout, socket.gaierror, EOFError))
        or isinstance(e, amqp.exceptions.RecoverableConnectionError)
        or (
            isinstance(e, OSError)
            and e.errno
            in {
                errno.ECONNABORTED,
                errno.ECONNREFUSED,
                errno.ECONNRESET,
                errno.EHOSTUNREACH,
                errno.ENETDOWN,
                errno.ENETUNREACH,
                errno.ENOTCONN,
                errno.EPIPE,
                errno.ETIMEDOUT,
            }
        )
        or is_amqplib_ioerror(e)
    )


def reset_connection():
    """Discard cached transport state without waiting for a broker close handshake."""
    global _connection
    connection, _connection = _connection, None
    if connection is not None:
        try:
            connection.collect()
        except Exception:
            logger.warning("AMQP connection cleanup failed", exc_info=True)


def get_connection():
    """Return a connected client, or None on a recoverable transport failure."""
    global _connection
    if _connection is not None:
        if _connection.connected:
            return _connection
        logger.warning("Discarding disconnected AMQP connection to %s", config.amqp_creds["host"])
        reset_connection()
    try:
        if "username" in config.amqp_creds and "password" in config.amqp_creds:
            _connection = amqp.Connection(
                host=config.amqp_creds["host"],
                userid=config.amqp_creds["username"],
                password=config.amqp_creds["password"],
                connect_timeout=10,
            )
        else:
            _connection = amqp.Connection(host=config.amqp_creds["host"], connect_timeout=10)
        _connection.connect()
        logger.info("AMQP connected to %s", config.amqp_creds["host"])
        return _connection
    except Exception as e:
        logger.exception("AMQP connection to %s failed", config.amqp_creds["host"])
        reset_connection()
        if is_amqplib_connection_error(e):
            return None
        # Unknown error mode : don't hide it.
        raise


def get_queue_length(queue: str) -> int | None:
    channel = None
    try:
        connection = get_connection()
        if connection is None:
            logger.error("Cannot get queue length for queue %s: AMQP unavailable", queue)
            return None
        channel = connection.channel()
        _, message_count, _ = channel.queue_declare(queue=queue, passive=True)
        return message_count
    except amqp.exceptions.NotFound:
        logger.debug("Queue %s does not exist", queue)
        return None
    except amqplib_error_types as error:
        logger.exception("Failed to get queue length for %s", queue)
        if not is_amqplib_connection_error(error):
            raise
        reset_connection()
        return None
    finally:
        _close_channel_safely(channel)


def enqueue(message: str, queue: str):
    channel = None
    try:
        connection = get_connection()
        if connection is None:
            logger.error("Cannot enqueue %s on %s: AMQP unavailable", message, queue)
            return False
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True, auto_delete=False)
        # We'll use this timestamp to measure how long it takes to process a
        # retrace, from receiving the core file to writing the data back to
        # Cassandra.
        body = amqp.Message(message, timestamp=int(datetime.now(timezone.utc).timestamp()))
        # Persistent
        body.properties["delivery_mode"] = 2
        channel.basic_publish(body, exchange="", routing_key=queue)
        logger.info("%s added to %s queue", message, queue)
        return True
    except amqplib_error_types as e:
        logger.exception("Failed to enqueue %s on %s", message, queue)
        if not is_amqplib_connection_error(e):
            raise
        # Could not connect / interrupted connection
        reset_connection()
        return False
    finally:
        _close_channel_safely(channel)


def _close_channel_safely(channel: amqp.Channel | None):
    if channel is None:
        return
    try:
        channel.close()
    except Exception as error:
        logger.warning("AMQP channel cleanup failed", exc_info=True)
        if is_amqplib_connection_error(error):
            reset_connection()
