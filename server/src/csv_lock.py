"""
from contextlib import contextmanager
from pathlib import Path
import threading
import fasteners

LOCK_PATH = Path(__file__).parent.parent / "outputs" / ".sensor_readings.lock"
THREAD_LOCK = threading.RLock()
PROCESS_LOCK = fasteners.InterProcessLock(str(LOCK_PATH))

@contextmanager
def csv_lock():
    with THREAD_LOCK:
        with PROCESS_LOCK:
            yield
"""
