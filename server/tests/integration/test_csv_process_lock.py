import multiprocessing
from pathlib import Path
from unittest import mock

import pytest

from server.src import csv_lock as csv_lock_module


pytestmark = pytest.mark.integration


def _lock_worker(csv_file, attempting, acquired, release):
    from server.src.csv_lock import csv_lock

    attempting.set()
    with csv_lock(Path(csv_file)):
        acquired.set()
        release.wait(timeout=5)


def test_csv_lock_is_reentrant_without_reacquiring_process_lock(tmp_path):
    process_lock = mock.Mock()
    process_lock.acquire.return_value = True

    with mock.patch.object(
        csv_lock_module.fasteners,
        "InterProcessLock",
        return_value=process_lock,
    ):
        with csv_lock_module.csv_lock(tmp_path / "sensor_readings.csv"):
            with csv_lock_module.csv_lock(tmp_path / "sensor_readings.csv"):
                pass

    process_lock.acquire.assert_called_once_with()
    process_lock.release.assert_called_once_with()


def test_csv_lock_raises_when_process_lock_cannot_be_acquired(tmp_path):
    process_lock = mock.Mock()
    process_lock.acquire.return_value = False

    with (
        mock.patch.object(
            csv_lock_module.fasteners,
            "InterProcessLock",
            return_value=process_lock,
        ),
        pytest.raises(RuntimeError, match="CSV lock could not be acquired"),
    ):
        with csv_lock_module.csv_lock(tmp_path / "sensor_readings.csv"):
            pass

    process_lock.release.assert_not_called()


def test_csv_lock_blocks_another_process_until_release(tmp_path):
    context = multiprocessing.get_context("spawn")
    csv_file = tmp_path / "sensor_readings.csv"
    first_attempting = context.Event()
    first_acquired = context.Event()
    release_first = context.Event()
    second_attempting = context.Event()
    second_acquired = context.Event()
    release_second = context.Event()
    first = context.Process(
        target=_lock_worker,
        args=(csv_file, first_attempting, first_acquired, release_first),
    )
    second = context.Process(
        target=_lock_worker,
        args=(csv_file, second_attempting, second_acquired, release_second),
    )

    try:
        first.start()
        assert first_attempting.wait(timeout=5)
        assert first_acquired.wait(timeout=5)

        second.start()
        assert second_attempting.wait(timeout=5)
        assert not second_acquired.wait(timeout=0.25)

        release_first.set()
        assert second_acquired.wait(timeout=5)
        release_second.set()

        first.join(timeout=5)
        second.join(timeout=5)
        assert first.exitcode == 0
        assert second.exitcode == 0
    finally:
        release_first.set()
        release_second.set()
        for process in (first, second):
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
