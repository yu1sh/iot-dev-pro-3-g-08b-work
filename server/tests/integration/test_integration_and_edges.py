import csv
import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock
from uuid import uuid4

import pytest

from client.src import sensor_client
from server.src import csv_writter as server_csv
from server.src import sensor_receiver
from server.src import web_dashboard

pytestmark = pytest.mark.integration


class ScriptedSocket:
    def __init__(self, chunks=(), send_error=None):
        self.chunks = list(chunks)
        self.send_error = send_error
        self.sent = bytearray()
        self.closed = False

    def recv(self, size):
        if not self.chunks:
            return b""
        result = self.chunks.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def sendall(self, data):
        if self.send_error is not None:
            raise self.send_error
        self.sent.extend(data)

    def close(self):
        self.closed = True


def payload(message_id=None, **overrides):
    item = {
        "message_id": message_id or str(uuid4()),
        "timestamp": "20260723-120000",
        "raspi_id": "raspi-ci",
        "sensor_id": "dht-ci",
        "tempe_dht_1": 24.5,
        "humid_dht_1": 56.0,
        "status": "OK",
    }
    item.update(overrides)
    return [item]


@pytest.fixture(autouse=True)
def isolated_receiver_state(tmp_path, monkeypatch):
    monkeypatch.setattr(server_csv, "CSV_DIR", tmp_path)
    monkeypatch.setattr(server_csv, "CSV_FILE", tmp_path / "sensor_readings.csv")
    sensor_receiver.PROCESSED_MESSAGES.clear()
    yield
    sensor_receiver.PROCESSED_MESSAGES.clear()


def test_real_tcp_client_to_receiver_writes_csv_and_returns_ack(monkeypatch):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    host, port = listener.getsockname()
    server_errors = []

    def receive_once():
        try:
            connection, address = listener.accept()
            connection.settimeout(2)
            sensor_receiver.handle_client_connection(connection, address)
        except BaseException as exc:
            server_errors.append(exc)
        finally:
            listener.close()

    thread = threading.Thread(target=receive_once)
    thread.start()
    reading = payload()
    monkeypatch.setattr(sensor_client, "WAIT_INTERVAL_RETRY", 0)

    assert sensor_client.send_sensor_payload(host, port, reading) is True
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert server_errors == []
    with server_csv.CSV_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [
        ["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"],
        ["20260723-120000", "raspi-ci", "24.5", "56.0", "dht-ci", "OK"],
    ]


def test_concurrent_unique_messages_are_each_written_once():
    messages = [
        (
            str(uuid4()),
            [f"20260723-1200{index:02d}", "raspi-ci", 24.5, 56.0, "dht-ci", "OK"],
            f"fingerprint-{index}".encode(),
        )
        for index in range(20)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda args: sensor_receiver.save_sensor_message_idempotent(*args),
                messages,
            )
        )

    assert results == [True] * len(messages)
    with server_csv.CSV_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == len(messages) + 1
    assert len({row[0] for row in rows[1:]}) == len(messages)


def test_concurrent_duplicate_message_is_written_once():
    message_id = str(uuid4())
    row = ["20260723-120000", "raspi-ci", 24.5, 56.0, "dht-ci", "OK"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: sensor_receiver.save_sensor_message_idempotent(
                    message_id,
                    row,
                    b"same",
                ),
                range(12),
            )
        )

    assert results.count(True) == 1
    assert results.count(False) == 11
    with server_csv.CSV_FILE.open(newline="", encoding="utf-8") as f:
        assert len(list(csv.reader(f))) == 2


def test_processed_message_cache_evicts_oldest(monkeypatch):
    monkeypatch.setattr(sensor_receiver, "MAX_PROCESSED_MESSAGES", 1)
    first = str(uuid4())
    second = str(uuid4())
    row = ["20260723-120000", "raspi-ci", 24.5, 56.0, "dht-ci", "OK"]

    sensor_receiver.save_sensor_message_idempotent(first, row, b"first")
    sensor_receiver.save_sensor_message_idempotent(second, row, b"second")

    assert list(sensor_receiver.PROCESSED_MESSAGES) == [second]


@pytest.mark.parametrize(
    ("chunks", "expected_code"),
    [
        ([b"\n"], "invalid_payload"),
        ([b"not-json\n"], "invalid_payload"),
        ([b"x" * (sensor_receiver.MAX_PAYLOAD_SIZE + 1) + b"\n"], "payload_too_large"),
        ([socket.timeout("timeout")], "timeout"),
    ],
)
def test_protocol_errors_return_machine_readable_response(chunks, expected_code):
    client = ScriptedSocket(chunks)

    sensor_receiver.handle_client_connection(client, ("127.0.0.1", 50000))

    assert json.loads(client.sent) == {
        "status": "error",
        "code": expected_code,
    }
    assert client.closed


def test_conflicting_duplicate_returns_message_id_and_error_code():
    message_id = str(uuid4())
    encoded = json.dumps(payload(message_id)).encode() + b"\n"
    client = ScriptedSocket([encoded])

    with mock.patch.object(
        sensor_receiver,
        "save_sensor_message_idempotent",
        side_effect=sensor_receiver.DuplicateMessageConflictError,
    ):
        sensor_receiver.handle_client_connection(client, ("127.0.0.1", 50000))

    assert json.loads(client.sent) == {
        "status": "error",
        "message_id": message_id,
        "code": "message_id_conflict",
    }


@pytest.mark.parametrize(
    "chunks",
    [
        [b"\xff\n"],
        [b"\n"],
        [socket.timeout("timeout")],
    ],
)
def test_error_response_send_failure_is_contained(chunks):
    client = ScriptedSocket(chunks, send_error=OSError("send failed"))

    sensor_receiver.handle_client_connection(client, ("127.0.0.1", 50000))

    assert client.closed


def test_oversize_and_conflict_response_send_failures_are_contained():
    oversized = ScriptedSocket(
        [b"x" * (sensor_receiver.MAX_PAYLOAD_SIZE + 1)],
        send_error=OSError("send failed"),
    )
    sensor_receiver.handle_client_connection(oversized, ("127.0.0.1", 50000))
    assert oversized.closed

    message_id = str(uuid4())
    conflict = ScriptedSocket(
        [json.dumps(payload(message_id)).encode() + b"\n"],
        send_error=OSError("send failed"),
    )
    with mock.patch.object(
        sensor_receiver,
        "save_sensor_message_idempotent",
        side_effect=sensor_receiver.DuplicateMessageConflictError,
    ):
        sensor_receiver.handle_client_connection(conflict, ("127.0.0.1", 50000))
    assert conflict.closed


def test_socket_and_unexpected_receive_errors_are_contained():
    for error in (OSError("read failed"), RuntimeError("unexpected")):
        client = ScriptedSocket([error])
        sensor_receiver.handle_client_connection(client, ("127.0.0.1", 50000))
        assert client.closed


def test_parse_rejects_non_object_and_noncanonical_uuid():
    with pytest.raises(TypeError):
        sensor_receiver.parse_sensor_payload(json.dumps(["not-an-object"]))

    uppercase_id = str(uuid4()).upper()
    with pytest.raises(ValueError, match="canonical UUID"):
        sensor_receiver.parse_sensor_payload(json.dumps(payload(uppercase_id)))


def test_actual_flask_dashboard_renders_template_and_normalizes_csv(tmp_path, monkeypatch):
    csv_file = tmp_path / "sensor_readings.csv"
    csv_file.write_text(
        "bad,header\n"
        "20260723-120000,raspi-ci,24.5,56.0,dht-ci,OK\n"
        "broken,row\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(web_dashboard, "CSV_FILE", csv_file)

    response = web_dashboard.app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "温湿度情報" in html
    assert "20260723-120000" in html
    assert "raspi-ci" in html
    with csv_file.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 2


def test_actual_flask_dashboard_handles_missing_csv_and_downloads_it(
    tmp_path,
    monkeypatch,
):
    csv_file = tmp_path / "nested" / "sensor_readings.csv"
    monkeypatch.setattr(web_dashboard, "CSV_FILE", csv_file)
    client = web_dashboard.app.test_client()

    index_response = client.get("/")
    download_response = client.get("/files")

    assert index_response.status_code == 200
    assert csv_file.exists()
    assert download_response.status_code == 200
    disposition = download_response.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert "sensor_readings_" in disposition


def test_server_startup_and_keyboard_interrupt_shutdown(monkeypatch):
    waiting_socket = mock.Mock()
    fake_thread = mock.Mock()
    monkeypatch.setattr(sensor_receiver.socket, "socket", mock.Mock(return_value=waiting_socket))
    monkeypatch.setattr(sensor_receiver.threading, "Thread", mock.Mock(return_value=fake_thread))
    monkeypatch.setattr(sensor_receiver.time, "sleep", mock.Mock(side_effect=KeyboardInterrupt))

    sensor_receiver.server("127.0.0.1", 8765)

    waiting_socket.bind.assert_called_once_with(("127.0.0.1", 8765))
    waiting_socket.listen.assert_called_once_with(5)
    fake_thread.start.assert_called_once_with()
    fake_thread.join.assert_called_once_with()
    waiting_socket.close.assert_called_once_with()


def test_server_load_config(monkeypatch):
    monkeypatch.setattr(
        sensor_receiver,
        "load_required_env",
        mock.Mock(return_value={"SERVER_IP": "127.0.0.1", "PORT_NUMBER": "8765"}),
    )
    monkeypatch.setattr(sensor_receiver, "parse_int_env", mock.Mock(return_value=8765))

    assert sensor_receiver.load_config() == ("127.0.0.1", 8765)


def test_server_main_applies_cli_overrides(monkeypatch):
    monkeypatch.setattr(sensor_receiver, "load_config", mock.Mock(return_value=("0.0.0.0", 8000)))
    run = mock.Mock()
    monkeypatch.setattr(sensor_receiver, "server", run)
    monkeypatch.setattr(
        sensor_receiver.sys,
        "argv",
        ["sensor-receiver", "-h", "127.0.0.1", "-p", "9000"],
    )

    sensor_receiver.main()

    run.assert_called_once_with("127.0.0.1", 9000)


def test_dashboard_load_config_and_main(monkeypatch):
    monkeypatch.setenv("DEBUG_MODE", "true")
    assert web_dashboard.load_config() is True

    monkeypatch.setattr(web_dashboard, "load_config", mock.Mock(return_value=False))
    run = mock.Mock()
    monkeypatch.setattr(web_dashboard.app, "run", run)
    web_dashboard.main()
    run.assert_called_once_with(
        host="0.0.0.0",
        port=5001,
        debug=False,
        use_reloader=False,
    )


def test_systemd_unit_has_network_order_restart_and_absolute_exec_path():
    unit_file = (
        Path(__file__).resolve().parents[3]
        / "systemd"
        / "iot-sensor_client.service"
    )
    text = unit_file.read_text(encoding="utf-8")

    assert "After=network-online.target" in text
    assert "Restart=always" in text
    assert "ExecStart=/" in text
    assert "sensor_client.py" in text
