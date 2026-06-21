import csv
from pathlib import Path

from logger_setup import setup_logger

logger = setup_logger(__name__)

CSV_FILE = Path(__file__).parent.parent / "outputs" / "sensor_readings.csv"


def load_csv(filepath):
    try:
        with open(filepath) as f:
            all_data_iter = csv.reader(f)
            row_count = sum(1 for row in all_data_iter)
        logger.info("Loaded CSV file path=%s rows=%s", filepath, row_count)
    except FileNotFoundError:
        logger.info("CSV file not found. Creating new file path=%s", filepath)
        with open(filepath, mode='w') as f:
            write_iter = csv.writer(f)
            write_iter.writerow(["raspi_id", "tempe_dht_1", "humid_dht_1", "timestamp"])
        logger.info("Created CSV file path=%s", filepath)


def save_csv(filepath, data):
    try:
        with open(filepath, mode='a') as f:
            write_iter = csv.writer(f)
            for row in data:
                write_iter.writerow(row)
        logger.info("Saved CSV rows path=%s rows=%s", filepath, data)
    except OSError:
        logger.exception("Failed to save CSV path=%s rows=%s", filepath, data)
        raise
