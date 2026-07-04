#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeLogger:
    def __init__(self):
        self.messages = []

    def error(self, message, *args):
        self.messages.append(("error", message, args))

    def info(self, message, *args):
        self.messages.append(("info", message, args))


def load_module(module_name, file_path):
    original_dotenv = sys.modules.get("dotenv")
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = fake_load_dotenv
    sys.modules["dotenv"] = fake_dotenv

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        if original_dotenv is None:
            sys.modules.pop("dotenv", None)
        else:
            sys.modules["dotenv"] = original_dotenv
    return module


def fake_load_dotenv(env_file, verbose=True):
    for line in Path(env_file).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")
    return True


class EnvLoaderTestMixin:
    module_path = None

    def setUp(self):
        self.env_loader = load_module(self.module_name, self.module_path)
        self.logger = FakeLogger()

    @property
    def module_name(self):
        return self.module_path.parent.parent.name + "_env_loader_for_test"

    def test_load_required_env_reads_required_values(self):
        with TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("SERVER_IP=127.0.0.1\nPORT_NUMBER=8765\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                values = self.env_loader.load_required_env(
                    env_file,
                    ["SERVER_IP", "PORT_NUMBER"],
                    self.logger,
                )

        self.assertEqual(values["SERVER_IP"], "127.0.0.1")
        self.assertEqual(values["PORT_NUMBER"], "8765")

    def test_load_required_env_exits_when_env_file_is_missing(self):
        missing_file = Path("/tmp/not-existing-env-file-for-test")

        with self.assertRaises(SystemExit):
            self.env_loader.load_required_env(missing_file, ["SERVER_IP"], self.logger)

    def test_load_required_env_exits_when_required_key_is_missing(self):
        with TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("SERVER_IP=127.0.0.1\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(SystemExit):
                    self.env_loader.load_required_env(
                        env_file,
                        ["SERVER_IP", "PORT_NUMBER"],
                        self.logger,
                    )

    def test_parse_int_env_returns_integer(self):
        self.assertEqual(self.env_loader.parse_int_env("8765", "PORT_NUMBER", self.logger), 8765)

    def test_parse_int_env_exits_when_value_is_not_integer(self):
        with self.assertRaises(SystemExit):
            self.env_loader.parse_int_env("not-number", "PORT_NUMBER", self.logger)


class ClientEnvLoaderTest(EnvLoaderTestMixin, unittest.TestCase):
    module_path = REPO_ROOT / "client" / "src" / "env_loader.py"


class ServerEnvLoaderTest(EnvLoaderTestMixin, unittest.TestCase):
    module_path = REPO_ROOT / "server" / "src" / "env_loader.py"


if __name__ == "__main__":
    unittest.main()
