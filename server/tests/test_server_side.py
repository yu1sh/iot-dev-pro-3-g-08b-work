#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import importlib.util
import json
import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_SRC = REPO_ROOT / "server" / "src"


class FakeLogger:
    def __init__(self):
        self.messages = []

    def error(self, message, *args):
        self.messages.append(("error", message, args))

    def info(self, message, *args):
        self.messages.append(("info", message, args))


class FakeResponse:
    def __init__(self, data="", status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._data = data

    def get_data(self, as_text=False):
        if as_text:
            return self._data
        return self._data.encode("utf-8")


class FakeTestClient:
    def __init__(self, app):
        self.app = app

    def get(self, path):
        result = self.app.routes[path]()
        if isinstance(result, FakeResponse):
            return result
        return FakeResponse(result)


class FakeFlask:
    def __init__(self, name):
        self.name = name
        self.routes = {}

    def route(self, path, methods=None):
        def decorator(func):
            self.routes[path] = func
            return func
        return decorator

    def test_client(self):
        return FakeTestClient(self)

    def run(self, *args, **kwargs):
        pass


def fake_load_dotenv(env_file, verbose=True):
    for line in Path(env_file).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")
    return True


def fake_render_template(template_name, input_from_python=None, modified_date=None):
    rows = input_from_python or []
    return "\n".join(",".join(row) for row in rows)


def fake_send_file(file_path, as_attachment=False, download_name=None):
    return FakeResponse(
        Path(file_path).read_text(encoding="utf-8"),
        headers={
            "Content-Disposition": f"attachment; filename={download_name}",
        },
    )


def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ServerModuleTestCase(unittest.TestCase):
    def setUp(self):
        self.original_path = list(sys.path)
        self.original_modules = {
            name: sys.modules.get(name)
            for name in ("csv_writter", "logger_setup", "env_loader", "dotenv", "flask")
        }

        fake_dotenv = types.ModuleType("dotenv")
        fake_dotenv.load_dotenv = fake_load_dotenv
        sys.modules["dotenv"] = fake_dotenv

        fake_flask = types.ModuleType("flask")
        fake_flask.Flask = FakeFlask
        fake_flask.render_template = fake_render_template
        fake_flask.send_file = fake_send_file
        sys.modules["flask"] = fake_flask

        sys.path.insert(0, str(SERVER_SRC))
        self.server_csv = load_module("csv_writter", SERVER_SRC / "csv_writter.py")
        sys.modules["csv_writter"] = self.server_csv
        self.server_receiver = load_module("server_sensor_receiver_for_test", SERVER_SRC / "sensor_receiver.py")
        self.env_loader = load_module("server_env_loader_for_test", SERVER_SRC / "env_loader.py")

    def tearDown(self):
        sys.path = self.original_path
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class SensorReceiverStatusTest(ServerModuleTestCase):
    def test_status_check_returns_ok_for_normal_values(self):
        self.assertEqual(self.server_receiver.status_check(24.5, 56.0, "OK"), "OK")

    def test_status_check_returns_warning_for_temperature_out_of_range(self):
        self.assertEqual(self.server_receiver.status_check(61.0, 56.0, "OK"), "WARNING")
        self.assertEqual(self.server_receiver.status_check(-11.0, 56.0, "OK"), "WARNING")

    def test_status_check_returns_warning_for_humidity_warning_range(self):
        self.assertEqual(self.server_receiver.status_check(24.5, 9.0, "OK"), "WARNING")
        self.assertEqual(self.server_receiver.status_check(24.5, 96.0, "OK"), "WARNING")

    def test_status_check_returns_error_for_invalid_humidity(self):
        self.assertEqual(self.server_receiver.status_check(24.5, -1.0, "OK"), "ERROR")
        self.assertEqual(self.server_receiver.status_check(24.5, 101.0, "OK"), "ERROR")

    def test_status_check_returns_error_for_missing_fields(self):
        self.assertEqual(self.server_receiver.status_check(None, 56.0, "OK"), "ERROR")
        self.assertEqual(self.server_receiver.status_check(24.5, None, "OK"), "ERROR")
        self.assertEqual(self.server_receiver.status_check(24.5, 56.0, ""), "ERROR")


class SensorReceiverPayloadTest(ServerModuleTestCase):
    def test_parse_sensor_payload_converts_valid_json_to_csv_row(self):
        payload = [{
            "timestamp": "20260703-143000",
            "raspi_id": "raspi_001",
            "sensor_id": "dht_1",
            "tempe_dht_1": 24.5,
            "humid_dht_1": 56.0,
            "status": "OK",
        }]

        row = self.server_receiver.parse_sensor_payload(json.dumps(payload))

        self.assertEqual(row, ["20260703-143000", "raspi_001", 24.5, 56.0, "dht_1", "OK"])

    def test_parse_sensor_payload_overwrites_status_after_range_check(self):
        payload = [{
            "timestamp": "20260703-143000",
            "raspi_id": "raspi_001",
            "sensor_id": "dht_1",
            "tempe_dht_1": 61.0,
            "humid_dht_1": 56.0,
            "status": "OK",
        }]

        row = self.server_receiver.parse_sensor_payload(json.dumps(payload))

        self.assertEqual(row[-1], "WARNING")

    def test_parse_sensor_payload_rejects_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            self.server_receiver.parse_sensor_payload("not-json")

    def test_parse_sensor_payload_rejects_empty_list(self):
        with self.assertRaises(IndexError):
            self.server_receiver.parse_sensor_payload("[]")

    def test_parse_sensor_payload_rejects_missing_required_key(self):
        with self.assertRaises(KeyError):
            self.server_receiver.parse_sensor_payload(json.dumps([{"timestamp": "20260703-143000"}]))


class ServerCsvTest(ServerModuleTestCase):
    def test_load_csv_creates_file_with_header_when_missing(self):
        with TemporaryDirectory() as tmp_dir:
            self.server_csv.CSV_DIR = Path(tmp_dir)
            self.server_csv.CSV_FILE = Path(tmp_dir) / "sensor_readings.csv"

            self.server_csv.load_csv()

            with open(self.server_csv.CSV_FILE, newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(rows, [["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"]])

    def test_save_sensor_payload_creates_header_and_saves_checked_row(self):
        payload = [{
            "timestamp": "20260703-143000",
            "raspi_id": "raspi_001",
            "sensor_id": "dht_1",
            "tempe_dht_1": 24.5,
            "humid_dht_1": 101.0,
            "status": "OK",
        }]

        with TemporaryDirectory() as tmp_dir:
            self.server_csv.CSV_DIR = Path(tmp_dir)
            self.server_csv.CSV_FILE = Path(tmp_dir) / "sensor_readings.csv"

            saved_row = self.server_receiver.save_sensor_payload(json.dumps(payload))

            with open(self.server_csv.CSV_FILE, newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(saved_row[-1], "ERROR")
        self.assertEqual(rows[0], ["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"])
        self.assertEqual(rows[1], ["20260703-143000", "raspi_001", "24.5", "101.0", "dht_1", "ERROR"])


class ServerEnvLoaderTest(ServerModuleTestCase):
    def test_load_required_env_reads_server_config(self):
        with TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("SERVER_IP=0.0.0.0\nPORT_NUMBER=8765\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                values = self.env_loader.load_required_env(env_file, ["SERVER_IP", "PORT_NUMBER"], FakeLogger())

        self.assertEqual(values["SERVER_IP"], "0.0.0.0")
        self.assertEqual(self.env_loader.parse_int_env(values["PORT_NUMBER"], "PORT_NUMBER", FakeLogger()), 8765)

    def test_load_required_env_exits_when_required_key_is_missing(self):
        with TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("SERVER_IP=0.0.0.0\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(SystemExit):
                    self.env_loader.load_required_env(env_file, ["SERVER_IP", "PORT_NUMBER"], FakeLogger())


class WebDashboardTest(ServerModuleTestCase):
    def setUp(self):
        super().setUp()
        self.web_dashboard = load_module("server_web_dashboard_for_test", SERVER_SRC / "web_dashboard.py")

    def test_index_displays_rows_from_sensor_csv(self):
        with TemporaryDirectory() as tmp_dir:
            self.web_dashboard.CSV_DIR = Path(tmp_dir)
            self.web_dashboard.CSV_FILE = Path(tmp_dir) / "sensor_readings.csv"
            self.web_dashboard.CSV_FILE.write_text(
                "timestamp,raspi_id,dht_temp,dht_humid,sensor_id,status\n"
                "20260703-143000,raspi_001,24.5,56.0,dht_1,OK\n",
                encoding="utf-8",
            )

            client = self.web_dashboard.app.test_client()
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("20260703-143000", response.get_data(as_text=True))
        self.assertIn("raspi_001", response.get_data(as_text=True))

    def test_download_returns_sensor_csv_as_attachment(self):
        with TemporaryDirectory() as tmp_dir:
            self.web_dashboard.CSV_DIR = Path(tmp_dir)
            self.web_dashboard.CSV_FILE = Path(tmp_dir) / "sensor_readings.csv"
            self.web_dashboard.CSV_FILE.write_text(
                "timestamp,raspi_id,dht_temp,dht_humid,sensor_id,status\n",
                encoding="utf-8",
            )

            client = self.web_dashboard.app.test_client()
            response = client.get("/files")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("sensor_readings_", response.headers["Content-Disposition"])


if __name__ == "__main__":
    unittest.main()
