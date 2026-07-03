#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


CLIENT_SRC = Path(__file__).resolve().parents[1] / "src"
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

import csv_writter
import sensor_client


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


if __name__ == "__main__":
    unittest.main()
