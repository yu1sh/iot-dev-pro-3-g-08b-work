from contextlib import contextmanager
from pathlib import Path
import threading

import fasteners


_THREAD_LOCK = threading.RLock()
_LOCK_STATE = threading.local()


def _get_lock_path(csv_file):
    csv_path = Path(csv_file).resolve()
    return csv_path.with_name(f".{csv_path.name}.lock")


@contextmanager
def csv_lock(csv_file):
    """同じCSVを扱うスレッドとプロセスを相互排他にする。"""
    lock_path = _get_lock_path(csv_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with _THREAD_LOCK:
        held_locks = getattr(_LOCK_STATE, "held_locks", {})
        current_depth = held_locks.get(lock_path, 0)
        if current_depth:
            held_locks[lock_path] = current_depth + 1
            try:
                yield
            finally:
                held_locks[lock_path] -= 1
            return

        process_lock = fasteners.InterProcessLock(str(lock_path))
        if not process_lock.acquire():
            raise RuntimeError(f"CSV lock could not be acquired: {lock_path}")
        held_locks[lock_path] = 1
        _LOCK_STATE.held_locks = held_locks
        try:
            yield
        finally:
            del held_locks[lock_path]
            process_lock.release()
