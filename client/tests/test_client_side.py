#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


CLIENT_SRC = Path(__file__).resolve().parents[1] / "src"
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_SRC = REPO_ROOT / "server" / "src"
sys.path.insert(0, str(CLIENT_SRC))


class FakeDHT22CRCError(Exception):
    pass


class FakeDHT22MissingDataError(Exception):
    pass


class FakeDHT22:
    def __init__(self, gpio):
        self.gpio = gpio

    def read(self):
        return 24.5, 56.0, 80


fake_dht22_module = types.ModuleType("dht22_takemoto")
fake_dht22_module.DHT22 = FakeDHT22
fake_dht22_module.DHT22CRCError = FakeDHT22CRCError
fake_dht22_module.DHT22MissingDataError = FakeDHT22MissingDataError
sys.modules["dht22_takemoto"] = fake_dht22_module

fake_dotenv_module = types.ModuleType("dotenv")
fake_dotenv_module.load_dotenv = lambda *args, **kwargs: True
sys.modules["dotenv"] = fake_dotenv_module

import csv_writter
import sensor_client
sensor_client.dht22 = fake_dht22_module


def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_server_modules():
    original_csv_writter = sys.modules.get("csv_writter")
    original_logger_setup = sys.modules.get("logger_setup")
    server_csv = load_module("server_csv_writter_for_test", SERVER_SRC / "csv_writter.py")
    server_logger = load_module("server_logger_setup_for_test", SERVER_SRC / "logger_setup.py")

    sys.modules["csv_writter"] = server_csv
    sys.modules["logger_setup"] = server_logger
    try:
        server_receiver = load_module("server_sensor_receiver_for_test", SERVER_SRC / "sensor_receiver.py")
    finally:
        if original_csv_writter is None:
            sys.modules.pop("csv_writter", None)
        else:
            sys.modules["csv_writter"] = original_csv_writter

        if original_logger_setup is None:
            sys.modules.pop("logger_setup", None)
        else:
            sys.modules["logger_setup"] = original_logger_setup

    return server_csv, server_receiver


class FailingSocket:
    connect_count = 0

    def setsockopt(self, *args):
        pass

    def settimeout(self, *args):
        pass

    def connect(self, *args):
        type(self).connect_count += 1
        raise OSError("connection failed for test")

    def close(self):
        pass


class SensorClientSideTest(unittest.TestCase):
    def test_get_dht_data_returns_temperature_and_humidity(self):
        sensor_client.dht22_instance = FakeDHT22(gpio=26)

        result = sensor_client.get_dht_data()

        self.assertEqual(result, (24.5, 56.0))

    def test_get_dht_data_returns_none_when_sensor_raises_error(self):
        class BrokenDHT22:
            def read(self):
                raise FakeDHT22CRCError()

        sensor_client.dht22_instance = BrokenDHT22()

        with mock.patch.object(sensor_client.time, "sleep"):
            result = sensor_client.get_dht_data()

        self.assertIsNone(result)

    def test_build_sensor_payload_has_required_fields_and_json_serializes(self):
        payload = sensor_client.build_sensor_payload(
            "20260703-143000",
            24.5,
            56.0,
            "OK",
        )

        self.assertEqual(
            payload,
            [{
                "timestamp": "20260703-143000",
                "raspi_id": sensor_client.RASPI_ID,
                "sensor_id": sensor_client.SENSOR_ID,
                "tempe_dht_1": 24.5,
                "humid_dht_1": 56.0,
                "status": "OK",
            }],
        )
        self.assertIsInstance(json.dumps(payload), str)

    def test_save_local_csv_creates_header_and_data_row(self):
        with TemporaryDirectory() as tmp_dir:
            csv_writter.CSV_DIR = Path(tmp_dir)
            csv_writter.CSV_FILE = Path(tmp_dir) / "failed_sensor_readings.csv"

            sensor_client.save_local_csv("20260703-143000", 24.5, 56.0, "SEND_FAILED")

            with open(csv_writter.CSV_FILE, newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(
            rows[0],
            ["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"],
        )
        self.assertEqual(
            rows[1],
            ["20260703-143000", sensor_client.RASPI_ID, "24.5", "56.0", sensor_client.SENSOR_ID, "SEND_FAILED"],
        )

    def test_save_local_csv_can_store_warning_and_error_status(self):
        with TemporaryDirectory() as tmp_dir:
            csv_writter.CSV_DIR = Path(tmp_dir)
            csv_writter.CSV_FILE = Path(tmp_dir) / "failed_sensor_readings.csv"

            sensor_client.save_local_csv("20260703-143000", 61.0, 56.0, "WARNING")
            sensor_client.save_local_csv("20260703-143010", None, None, "ERROR")

            with open(csv_writter.CSV_FILE, newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(rows[1][-1], "WARNING")
        self.assertEqual(rows[2][-1], "ERROR")
        self.assertEqual(rows[2][2:4], ["", ""])

    def test_send_failure_retries_and_saves_send_failed_status(self):
        with TemporaryDirectory() as tmp_dir:
            csv_writter.CSV_DIR = Path(tmp_dir)
            csv_writter.CSV_FILE = Path(tmp_dir) / "failed_sensor_readings.csv"
            FailingSocket.connect_count = 0
            payload = sensor_client.build_sensor_payload(
                "20260703-143000",
                24.5,
                56.0,
                "OK",
            )

            with mock.patch("socket.socket", return_value=FailingSocket()):
                with mock.patch.object(sensor_client.time, "sleep"):
                    result = sensor_client.send_sensor_payload("127.0.0.1", 8765, payload)

            with open(csv_writter.CSV_FILE, newline="") as f:
                rows = list(csv.reader(f))

        self.assertFalse(result)
        self.assertEqual(FailingSocket.connect_count, sensor_client.MAX_SEND_RETRY + 1)
        self.assertEqual(rows[1][-1], "SEND_FAILED")
        self.assertEqual(payload[0]["status"], "SEND_FAILED")


class SensorReceiverServerSideTest(unittest.TestCase):
    def setUp(self):
        self.server_csv, self.sensor_receiver = load_server_modules()

    def test_status_check_returns_ok_warning_and_error(self):
        self.assertEqual(self.sensor_receiver.status_check(24.5, 56.0, "OK"), "OK")
        self.assertEqual(self.sensor_receiver.status_check(61.0, 56.0, "OK"), "WARNING")
        self.assertEqual(self.sensor_receiver.status_check(24.5, 101.0, "OK"), "ERROR")
        self.assertEqual(self.sensor_receiver.status_check(None, 56.0, "OK"), "ERROR")

    def test_server_parses_client_payload_into_csv_row(self):
        payload = sensor_client.build_sensor_payload(
            "20260703-143000",
            24.5,
            56.0,
            "OK",
        )

        row = self.sensor_receiver.parse_sensor_payload(json.dumps(payload))

        self.assertEqual(
            row,
            ["20260703-143000", sensor_client.RASPI_ID, 24.5, 56.0, sensor_client.SENSOR_ID, "OK"],
        )

    def test_server_csv_creates_header_and_saves_received_payload(self):
        payload = sensor_client.build_sensor_payload(
            "20260703-143000",
            61.0,
            56.0,
            "OK",
        )

        with TemporaryDirectory() as tmp_dir:
            self.server_csv.CSV_DIR = Path(tmp_dir)
            self.server_csv.CSV_FILE = Path(tmp_dir) / "sensor_readings.csv"

            saved_row = self.sensor_receiver.save_sensor_payload(json.dumps(payload))

            with open(self.server_csv.CSV_FILE, newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(
            rows[0],
            ["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"],
        )
        self.assertEqual(saved_row[-1], "WARNING")
        self.assertEqual(rows[1][-1], "WARNING")

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(json.JSONDecodeError):
            self.sensor_receiver.parse_sensor_payload("not-json")

    def test_missing_required_payload_key_is_rejected(self):
        payload = [{"timestamp": "20260703-143000"}]

        with self.assertRaises(KeyError):
            self.sensor_receiver.parse_sensor_payload(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
