#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv
from pathlib import Path
import threading
try:
    from .logger_setup import setup_logger
    from .env_loader import get_path_env
except ImportError:
    from logger_setup import setup_logger
    from env_loader import get_path_env

logger = setup_logger(__name__)

CSV_FILE = get_path_env(
    "CSV_FILE",
    Path(__file__).parent.parent / "outputs" / "sensor_readings.csv",
    "server",
)
CSV_DIR = CSV_FILE.parent
CSV_DIR.mkdir(parents=True, exist_ok=True)

CSV_LOCK = threading.Lock()

def load_csv():
    with CSV_LOCK:
        try:
            with open(CSV_FILE) as f:
                all_data_iter = csv.reader(f)
                row_count = sum(1 for row in all_data_iter)
            logger.info("Loaded CSV file path=%s rows=%s", CSV_FILE, row_count)
        except FileNotFoundError:
            logger.info("CSV file not found. Creating new file path=%s", CSV_FILE)
            with open(CSV_FILE, mode='w') as f:
                write_iter = csv.writer(f)
                write_iter.writerow(["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"])
            logger.info("Created CSV file path=%s", CSV_FILE)

def save_csv(data):
    with CSV_LOCK:
        try:
            with open(CSV_FILE, mode='a') as f:
                write_iter = csv.writer(f)
                for row in data:
                    write_iter.writerow(row)
            logger.info("Saved CSV rows path=%s rows=%s", CSV_FILE, data)
        except OSError:
            logger.exception("Failed to save CSV path=%s rows=%s", CSV_FILE, data)
            raise
