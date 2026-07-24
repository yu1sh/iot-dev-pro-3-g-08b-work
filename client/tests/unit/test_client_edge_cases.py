import json
import sys
from pathlib import Path
from unittest import mock

import pytest


CLIENT_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(CLIENT_SRC))

import sensor_client


class ChunkSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def recv(self, size):
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk


def test_load_config_and_initialize_sensor(tmp_path):
    fake_sensor = object()
    fake_driver = mock.Mock()
    fake_driver.DHT22.return_value = fake_sensor

    with (
        mock.patch.object(
            sensor_client,
            "load_required_env",
            return_value={
                "SERVER_IP": "127.0.0.1",
                "PORT_NUMBER": "8765",
                "RPI_ID": "raspi-ci",
                "SENSOR_ID": "dht-ci",
                "GPIO_NUMBER": "17",
            },
        ),
        mock.patch.object(
            sensor_client,
            "parse_int_env",
            side_effect=lambda value, _key, _logger: int(value),
        ),
    ):
        config = sensor_client.load_config()

    with mock.patch.object(sensor_client, "dht22", fake_driver):
        assert sensor_client.initialize_dht22(17) is fake_sensor
    assert config == {
        "server": "127.0.0.1",
        "waiting_port": 8765,
        "raspi_id": "raspi-ci",
        "sensor_id": "dht-ci",
        "gpio_number": 17,
    }
    fake_driver.DHT22.assert_called_once_with(gpio=17)


def test_lazy_driver_import_uses_available_module():
    original_driver = sensor_client.dht22
    sensor_client.dht22 = None
    try:
        assert sensor_client.load_dht22_module() is sys.modules["dht22_takemoto"]
        assert sensor_client.load_dht22_module() is sys.modules["dht22_takemoto"]
    finally:
        sensor_client.dht22 = original_driver


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        json.dumps({"status": "error"}).encode() + b"\n",
        b"not-json\n",
        b"\xff\n",
    ],
)
def test_receive_ack_rejects_closed_or_invalid_response(payload):
    chunks = [] if payload == b"" else [payload]
    error = ConnectionError if payload == b"" else (
        UnicodeDecodeError if payload == b"\xff\n" else ValueError
    )

    with pytest.raises(error):
        sensor_client.receive_ack(ChunkSocket(chunks), "expected-id")


def test_receive_ack_rejects_oversized_response_with_and_without_newline():
    oversized = b"x" * (sensor_client.MAX_ACK_SIZE + 1)

    with pytest.raises(ValueError, match="too large"):
        sensor_client.receive_ack(ChunkSocket([oversized]), "expected-id")
    with pytest.raises(ValueError, match="too large"):
        sensor_client.receive_ack(
            ChunkSocket([oversized + b"\n"]),
            "expected-id",
        )


def test_get_dht_data_handles_missing_data_and_unexpected_error():
    class MissingSensor:
        def read(self):
            raise sensor_client.dht22.DHT22MissingDataError()

    class BrokenSensor:
        def read(self):
            raise RuntimeError("unexpected")

    with mock.patch.object(sensor_client.time, "sleep"):
        sensor_client.dht22_instance = MissingSensor()
        assert sensor_client.get_dht_data() is None
        sensor_client.dht22_instance = BrokenSensor()
        assert sensor_client.get_dht_data() is None


def test_get_dht_data_initializes_sensor_when_needed():
    reading_sensor = mock.Mock()
    reading_sensor.read.return_value = (24.5, 56.0, 1)

    def initialize():
        sensor_client.dht22_instance = reading_sensor

    sensor_client.dht22_instance = None
    with mock.patch.object(sensor_client, "initialize_dht22", side_effect=initialize) as init:
        assert sensor_client.get_dht_data() == (24.5, 56.0)

    init.assert_called_once_with()


def test_client_loop_saves_sensor_failure_then_stops():
    with (
        mock.patch.object(
            sensor_client,
            "get_dht_data",
            side_effect=[None, KeyboardInterrupt],
        ),
        mock.patch.object(sensor_client, "save_local_csv") as save,
    ):
        sensor_client.client_test("127.0.0.1", 8765)

    save.assert_called_once()
    assert save.call_args.args[-1] == "ERROR"


def test_client_loop_builds_and_sends_one_reading_then_stops():
    with (
        mock.patch.object(
            sensor_client,
            "get_dht_data",
            side_effect=[(24.5, 56.0), KeyboardInterrupt],
        ),
        mock.patch.object(
            sensor_client,
            "build_sensor_payload",
            return_value=[{"message_id": "id"}],
        ) as build,
        mock.patch.object(sensor_client, "send_sensor_payload") as send,
        mock.patch.object(sensor_client.time, "sleep"),
    ):
        sensor_client.client_test("127.0.0.1", 8765)

    build.assert_called_once()
    send.assert_called_once_with("127.0.0.1", 8765, [{"message_id": "id"}])


def test_client_loop_contains_unexpected_error():
    with mock.patch.object(
        sensor_client,
        "get_dht_data",
        side_effect=RuntimeError("unexpected"),
    ):
        sensor_client.client_test("127.0.0.1", 8765)


def test_main_applies_config_and_cli_overrides():
    config = {
        "server": "config-host",
        "waiting_port": 8000,
        "raspi_id": "raspi-main",
        "sensor_id": "sensor-main",
        "gpio_number": 26,
    }
    with (
        mock.patch.object(sensor_client, "load_config", return_value=config),
        mock.patch.object(sensor_client, "initialize_dht22") as initialize,
        mock.patch.object(sensor_client, "client_test") as run,
        mock.patch.object(
            sys,
            "argv",
            ["sensor-client", "-h", "cli-host", "-p", "9000", "-m", "hello"],
        ),
    ):
        sensor_client.main()

    initialize.assert_called_once_with(26)
    run.assert_called_once_with("cli-host", 9000, "hello")
    assert sensor_client.RASPI_ID == "raspi-main"
    assert sensor_client.SENSOR_ID == "sensor-main"
