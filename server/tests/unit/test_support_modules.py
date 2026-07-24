import csv
import importlib.util
import io
import logging
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(("info", message, args))

    def warning(self, message, *args):
        self.messages.append(("warning", message, args))


def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def logger_name():
    name = f"logger_setup_test_{uuid4().hex}"
    yield name

    logger = logging.getLogger(name)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


@pytest.mark.parametrize(
    "module_path",
    [
        REPO_ROOT / "client" / "src" / "logger_setup.py",
        REPO_ROOT / "server" / "src" / "logger_setup.py",
    ],
)
def test_setup_logger_creates_log_file_and_does_not_duplicate_handlers(
    module_path, tmp_path, logger_name
):
    logger_setup = load_module(f"logger_setup_for_test_{uuid4().hex}", module_path)
    logger_setup.LOG_DIR = tmp_path / "logs"
    logger_setup.LOG_FILE = logger_setup.LOG_DIR / "application.log"

    logger = logger_setup.setup_logger(logger_name)

    assert logger_setup.LOG_DIR.is_dir()
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 2
    assert any(isinstance(handler, logging.FileHandler) for handler in logger.handlers)

    logger.info("test log message")
    for handler in logger.handlers:
        handler.flush()

    assert "test log message" in logger_setup.LOG_FILE.read_text(encoding="utf-8")
    assert logger_setup.setup_logger(logger_name).handlers == logger.handlers


@pytest.fixture
def csv_loader():
    return load_module(
        f"csv_loader_for_test_{uuid4().hex}",
        REPO_ROOT / "server" / "src" / "csv_loader.py",
    )


def read_csv_rows(csv_file):
    with csv_file.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_check_csv_creates_file_with_header_when_missing(csv_loader, tmp_path):
    csv_file = tmp_path / "outputs" / "sensor_readings.csv"

    csv_loader.check_csv(csv_file, FakeLogger())

    assert read_csv_rows(csv_file) == [csv_loader.CSV_HEADER]


def test_check_csv_normalizes_invalid_header_and_malformed_rows(csv_loader, tmp_path):
    csv_file = tmp_path / "sensor_readings.csv"
    csv_file.write_text(
        "invalid,header\n"
        "20260703-143000,raspi_001,24.5,56.0,dht_1,OK\n"
        "\n"
        "too,few,columns\n"
        "20260703-144000,raspi_002,25.0,57.0,dht_2,WARNING\n",
        encoding="utf-8",
    )

    csv_loader.check_csv(csv_file, FakeLogger())

    assert read_csv_rows(csv_file) == [
        csv_loader.CSV_HEADER,
        ["20260703-143000", "raspi_001", "24.5", "56.0", "dht_1", "OK"],
        ["20260703-144000", "raspi_002", "25.0", "57.0", "dht_2", "WARNING"],
    ]


def test_check_csv_keeps_valid_csv_unchanged(csv_loader, tmp_path):
    csv_file = tmp_path / "sensor_readings.csv"
    expected_rows = [
        csv_loader.CSV_HEADER,
        ["20260703-143000", "raspi_001", "24.5", "56.0", "dht_1", "OK"],
    ]
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(expected_rows)

    csv_loader.check_csv(csv_file, FakeLogger())

    assert read_csv_rows(csv_file) == expected_rows


def uploaded_csv(text):
    return SimpleNamespace(stream=io.BytesIO(text.encode("utf-8")))


def test_merge_uploaded_csv_inserts_in_timestamp_order_and_skips_duplicates(
    csv_loader, tmp_path
):
    csv_file = tmp_path / "sensor_readings.csv"
    csv_file.write_text(
        ",".join(csv_loader.CSV_HEADER) + "\n"
        "20260723-120010,raspi_001,25.0,57.0,dht_1,OK\n",
        encoding="utf-8",
    )
    upload = uploaded_csv(
        ",".join(csv_loader.CSV_HEADER) + "\n"
        "20260723-120020,raspi_001,26.0,58.0,dht_1,SEND_FAILED\n"
        "20260723-120000,raspi_001,24.0,56.0,dht_1,SEND_FAILED\n"
        "20260723-120010,raspi_001,25.0,57.0,dht_1,OK\n"
    )

    added, duplicates = csv_loader.merge_uploaded_csv(
        csv_file, upload, FakeLogger()
    )

    assert (added, duplicates) == (2, 1)
    assert [row[0] for row in read_csv_rows(csv_file)[1:]] == [
        "20260723-120000",
        "20260723-120010",
        "20260723-120020",
    ]


def test_merge_uploaded_csv_rejects_invalid_timestamp(csv_loader, tmp_path):
    upload = uploaded_csv(
        ",".join(csv_loader.CSV_HEADER) + "\n"
        "invalid,raspi_001,24.0,56.0,dht_1,SEND_FAILED\n"
    )

    with pytest.raises(csv_loader.CsvImportError, match="日時"):
        csv_loader.merge_uploaded_csv(
            tmp_path / "sensor_readings.csv", upload, FakeLogger()
        )
