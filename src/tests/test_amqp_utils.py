import errno
import logging
import socket
from datetime import datetime, timezone
from unittest.mock import Mock

import amqp
import pytest

from errortracker import amqp_utils


@pytest.mark.parametrize(
    "error, recoverable",
    [
        (ConnectionRefusedError("refused"), True),
        (ConnectionResetError("reset"), True),
        (BrokenPipeError("broken pipe"), True),
        (socket.timeout("timeout"), True),
        (socket.gaierror("lookup failed"), True),
        (EOFError("closed"), True),
        (OSError(errno.ENETUNREACH, "unreachable"), True),
        (IOError("Socket closed"), True),
        (amqp.exceptions.ConnectionForced("closed by broker"), True),
        (amqp.exceptions.NotAllowed("authentication failed"), False),
        (amqp.exceptions.AccessRefused("permission denied"), False),
        (amqp.exceptions.PreconditionFailed("queue mismatch"), False),
        (FileNotFoundError("missing file"), False),
        (ValueError("invalid configuration"), False),
    ],
)
def test_connection_failure_classification(error, recoverable):
    assert amqp_utils.is_amqplib_connection_error(error) is recoverable


@pytest.fixture
def connection_factory(monkeypatch):
    monkeypatch.setattr(amqp_utils, "_connection", None)
    monkeypatch.setattr(
        amqp_utils.config,
        "amqp_creds",
        {"host": "broker:5672", "username": "test", "password": "secret"},
    )
    factory = Mock()
    monkeypatch.setattr(amqp_utils.amqp, "Connection", factory)
    return factory


def test_connected_client_is_reused(connection_factory):
    connection = amqp_utils.get_connection()
    assert amqp_utils.get_connection() is connection
    connection_factory.assert_called_once_with(
        host="broker:5672", userid="test", password="secret", connect_timeout=10
    )
    connection.connect.assert_called_once_with()


def test_closed_client_is_replaced(connection_factory, caplog):
    stale = Mock(connected=False)
    amqp_utils._connection = stale
    assert amqp_utils.get_connection() is connection_factory.return_value
    stale.collect.assert_called_once_with()
    assert "Discarding disconnected AMQP connection" in caplog.text


@pytest.mark.parametrize("error", [ConnectionResetError("reset"), EOFError("closed")])
def test_failed_connection_is_logged_discarded_and_retried(connection_factory, caplog, error):
    failed = Mock()
    failed.connect.side_effect = error
    healthy = Mock()
    connection_factory.side_effect = [failed, healthy]

    assert amqp_utils.get_connection() is None
    assert amqp_utils._connection is None
    failed.collect.assert_called_once_with()
    assert "AMQP connection to broker:5672 failed" in caplog.text
    assert caplog.records[-1].exc_info is not None
    assert "secret" not in caplog.text
    assert amqp_utils.get_connection() is healthy


def test_unexpected_failure_propagates_despite_cleanup_error(connection_factory, caplog):
    connection = connection_factory.return_value
    error = amqp.exceptions.NotAllowed("authentication failed")
    connection.connect.side_effect = error
    connection.collect.side_effect = OSError("cleanup failed")

    with pytest.raises(amqp.exceptions.NotAllowed) as raised:
        amqp_utils.get_connection()

    assert raised.value is error
    assert amqp_utils._connection is None
    assert "AMQP connection cleanup failed" in caplog.text


def test_constructor_failure_does_not_leave_cached_client(connection_factory):
    connection_factory.side_effect = ConnectionRefusedError("refused")
    assert amqp_utils.get_connection() is None
    assert amqp_utils._connection is None


def test_enqueue_success_preserves_message_properties(connection_factory):
    channel = connection_factory.return_value.channel.return_value
    before = int(datetime.now(timezone.utc).timestamp())

    assert amqp_utils.enqueue("example-oops:swift", "retrace_amd64") is True

    after = int(datetime.now(timezone.utc).timestamp())
    channel.queue_declare.assert_called_once_with(
        queue="retrace_amd64", durable=True, auto_delete=False
    )
    channel.basic_publish.assert_called_once()
    args, kwargs = channel.basic_publish.call_args
    message = args[0]
    assert message.body == "example-oops:swift"
    assert message.properties["delivery_mode"] == 2
    assert before <= message.properties["timestamp"] <= after
    assert kwargs == {"exchange": "", "routing_key": "retrace_amd64"}
    channel.close.assert_called_once_with()
    connection_factory.return_value.collect.assert_not_called()


@pytest.mark.parametrize("operation", ["enqueue", "get_queue_length"])
def test_operation_handles_unavailable_connection(connection_factory, caplog, operation):
    connection = connection_factory.return_value
    connection.connect.side_effect = ConnectionRefusedError("broker unavailable")

    result = call_queue_operation(operation)

    assert result is (False if operation == "enqueue" else None)
    assert amqp_utils._connection is None
    connection.channel.assert_not_called()
    assert "retrace_amd64" in caplog.text
    assert any(record.exc_info for record in caplog.records)


def call_queue_operation(operation):
    if operation == "enqueue":
        return amqp_utils.enqueue("example-oops:swift", "retrace_amd64")
    return amqp_utils.get_queue_length("retrace_amd64")


@pytest.mark.parametrize(
    "operation, stage, error",
    [
        ("enqueue", "channel", ConnectionResetError("channel reset")),
        ("enqueue", "queue_declare", EOFError("declaration interrupted")),
        ("enqueue", "basic_publish", BrokenPipeError("publish interrupted")),
        ("get_queue_length", "channel", ConnectionResetError("channel reset")),
        ("get_queue_length", "queue_declare", EOFError("declaration interrupted")),
    ],
)
def test_transport_failure_resets_connection_and_logs_context(
    connection_factory, caplog, operation, stage, error
):
    connection = connection_factory.return_value
    channel = connection.channel.return_value
    target = connection if stage == "channel" else channel
    getattr(target, stage).side_effect = error

    result = call_queue_operation(operation)

    assert result is (False if operation == "enqueue" else None)
    assert amqp_utils._connection is None
    connection.collect.assert_called_once_with()
    assert "retrace_amd64" in caplog.text
    assert any(record.exc_info and record.exc_info[1] is error for record in caplog.records)
    if operation == "enqueue":
        assert "example-oops:swift" in caplog.text
    if stage == "channel":
        channel.close.assert_not_called()
    else:
        channel.close.assert_called_once_with()
    if stage == "basic_publish":
        channel.basic_publish.assert_called_once()
    else:
        channel.basic_publish.assert_not_called()


@pytest.mark.parametrize("operation", ["enqueue", "get_queue_length"])
@pytest.mark.parametrize(
    "stage, error_type",
    [
        ("channel", amqp.exceptions.NotAllowed),
        ("queue_declare", amqp.exceptions.PreconditionFailed),
        ("queue_declare", amqp.exceptions.AccessRefused),
        ("queue_declare", ValueError),
    ],
)
def test_nonrecoverable_operation_error_propagates(
    connection_factory, operation, stage, error_type
):
    connection = connection_factory.return_value
    channel = connection.channel.return_value
    error = error_type("not a recoverable transport failure")
    target = connection if stage == "channel" else channel
    getattr(target, stage).side_effect = error

    with pytest.raises(error_type) as raised:
        call_queue_operation(operation)

    assert raised.value is error
    if stage != "channel":
        channel.close.assert_called_once_with()


@pytest.mark.parametrize("count", [0, 7])
def test_queue_length_uses_passive_declaration(connection_factory, count):
    channel = connection_factory.return_value.channel.return_value
    channel.queue_declare.return_value = ("retrace_amd64", count, 1)

    assert amqp_utils.get_queue_length("retrace_amd64") == count

    channel.queue_declare.assert_called_once_with(queue="retrace_amd64", passive=True)
    channel.close.assert_called_once_with()
    connection_factory.return_value.collect.assert_not_called()


def test_missing_queue_is_unknown_without_connection_failure_log(connection_factory, caplog):
    connection = connection_factory.return_value
    channel = connection.channel.return_value
    channel.queue_declare.side_effect = amqp.exceptions.NotFound("missing queue")

    assert amqp_utils.get_queue_length("retrace_amd64") is None

    assert amqp_utils._connection is connection
    connection.collect.assert_not_called()
    channel.close.assert_called_once_with()
    assert not any(record.levelno >= logging.ERROR for record in caplog.records)


def test_safe_cleanup_accepts_missing_channel():
    amqp_utils._close_channel_safely(None)


@pytest.mark.parametrize("transport_failure", [True, False])
def test_cleanup_failure_is_logged_and_only_transport_errors_reset_connection(
    connection_factory, caplog, transport_failure
):
    connection = amqp_utils.get_connection()
    channel = connection.channel.return_value
    error = ConnectionResetError("close interrupted") if transport_failure else ValueError("bad close")
    channel.close.side_effect = error

    amqp_utils._close_channel_safely(channel)

    assert any(record.exc_info and record.exc_info[1] is error for record in caplog.records)
    if transport_failure:
        assert amqp_utils._connection is None
        connection.collect.assert_called_once_with()
    else:
        assert amqp_utils._connection is connection
        connection.collect.assert_not_called()


@pytest.mark.parametrize("operation", ["enqueue", "get_queue_length"])
def test_cleanup_failure_does_not_replace_success(connection_factory, operation, caplog):
    channel = connection_factory.return_value.channel.return_value
    channel.queue_declare.return_value = ("retrace_amd64", 7, 1)
    channel.close.side_effect = ConnectionResetError("cleanup failed")

    result = call_queue_operation(operation)

    assert result == (True if operation == "enqueue" else 7)
    assert amqp_utils._connection is None
    assert any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("operation", ["enqueue", "get_queue_length"])
def test_cleanup_failure_does_not_mask_original_exception(connection_factory, operation, caplog):
    channel = connection_factory.return_value.channel.return_value
    original = amqp.exceptions.PreconditionFailed("queue mismatch")
    cleanup = ConnectionResetError("cleanup failed")
    channel.queue_declare.side_effect = original
    channel.close.side_effect = cleanup

    with pytest.raises(amqp.exceptions.PreconditionFailed) as raised:
        call_queue_operation(operation)

    assert raised.value is original
    assert amqp_utils._connection is None
    assert any(record.exc_info and record.exc_info[1] is cleanup for record in caplog.records)


@pytest.mark.parametrize("operation", ["enqueue", "get_queue_length"])
def test_transport_failure_remains_handled_when_cleanup_also_fails(
    connection_factory, operation, caplog
):
    connection = connection_factory.return_value
    channel = connection.channel.return_value
    channel.queue_declare.side_effect = ConnectionResetError("operation failed")
    channel.close.side_effect = ValueError("cleanup failed")

    assert call_queue_operation(operation) is (False if operation == "enqueue" else None)
    assert amqp_utils._connection is None
    assert any(record.exc_info for record in caplog.records)


def test_enqueue_after_failed_publish_uses_fresh_connection(connection_factory):
    failed = Mock()
    failed.channel.return_value.basic_publish.side_effect = BrokenPipeError("broken pipe")
    healthy = Mock()
    connection_factory.side_effect = [failed, healthy]

    assert amqp_utils.enqueue("first-oops:swift", "retrace_amd64") is False
    assert amqp_utils.enqueue("next-oops:swift", "retrace_amd64") is True

    failed.collect.assert_called_once_with()
    failed.channel.return_value.basic_publish.assert_called_once()
    healthy.channel.return_value.basic_publish.assert_called_once()
