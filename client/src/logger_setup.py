import logging
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / f"sensor_client_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

def setup_logger(
    name: str
) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)

    logger_v = logging.getLogger(name)
    logger_v.setLevel(logging.INFO)

    if logger_v.handlers:
        return logger_v

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(filename)s: %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger_v.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger_v.addHandler(file_handler)

    return logger_v
