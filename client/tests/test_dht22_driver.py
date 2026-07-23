import importlib.util
import sys
import types
from pathlib import Path
from unittest import mock

import pytest


DRIVER_PATH = Path(__file__).resolve().parents[1] / "src" / "dht22_takemoto.py"


class FakeLgpio(types.ModuleType):
    SET_PULL_UP = 32

    def __init__(self):
        super().__init__("lgpio")
        self.calls = []
        self.read_values = iter(())

    def gpiochip_open(self, chip):
        self.calls.append(("open", chip))
        return 99

    def gpiochip_close(self, handle):
        self.calls.append(("close", handle))

    def gpio_claim_output(self, handle, gpio):
        self.calls.append(("output", handle, gpio))

    def gpio_claim_input(self, handle, gpio, pull):
        self.calls.append(("input", handle, gpio, pull))

    def gpio_write(self, handle, gpio, value):
        self.calls.append(("write", handle, gpio, value))

    def gpio_read(self, handle, gpio):
        self.calls.append(("read", handle, gpio))
        return next(self.read_values)


@pytest.fixture
def driver():
    fake_lgpio = FakeLgpio()
    original_lgpio = sys.modules.get("lgpio")
    sys.modules["lgpio"] = fake_lgpio

    spec = importlib.util.spec_from_file_location(
        "dht22_driver_for_test",
        DRIVER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        yield module, fake_lgpio
    finally:
        if original_lgpio is None:
            sys.modules.pop("lgpio", None)
        else:
            sys.modules["lgpio"] = original_lgpio


def bits_for_bytes(values):
    return [
        bool(value & (1 << shift))
        for value in values
        for shift in range(7, -1, -1)
    ]


def test_initialization_write_and_close_use_selected_gpio(driver):
    module, lgpio = driver
    sensor = module.DHT22(gpio=26)

    with mock.patch.object(module.time, "sleep") as sleep:
        sensor._DHT22__send_and_sleep(1, 0.02)
    sensor.close()

    assert ("open", 0) in lgpio.calls
    assert ("write", 99, 26, 1) in lgpio.calls
    assert ("close", 99) in lgpio.calls
    sleep.assert_called_once_with(0.02)


def test_bit_helpers_decode_bytes_and_checksum(driver):
    module, _ = driver
    sensor = module.DHT22(gpio=26)
    values = [0x02, 0x2B, 0x00, 0xF5]

    decoded = sensor._DHT22__bits_to_bytes(bits_for_bytes(values))

    assert decoded == values
    assert sensor._DHT22__calculate_checksum(decoded) == sum(values) & 0xFF
    assert sensor._DHT22__calculate_bits([2, 2, 5, 5]) == [
        False,
        False,
        True,
        True,
    ]


def test_pull_up_parser_extracts_data_pulse_lengths(driver):
    module, _ = driver
    sensor = module.DHT22(gpio=26)

    lengths = sensor._DHT22__parse_data_pull_up_lengths(
        [0, 1, 0, 1, 1, 0, 1, 1, 1, 0]
    )

    assert lengths == [2, 3]


def test_collect_input_stops_after_stable_signal(driver):
    module, lgpio = driver
    sensor = module.DHT22(gpio=26)
    lgpio.read_values = iter([0, 1] + [1] * 101)

    data = sensor._DHT22__collect_input()

    assert data[:2] == [0, 1]
    assert len(data) == 103


@pytest.mark.parametrize(
    ("raw_bytes", "expected"),
    [
        ([0x02, 0x30, 0x00, 0xF5], (24.5, 56.0)),
        ([0x02, 0x30, 0x80, 0x37], (-5.5, 56.0)),
    ],
)
def test_read_decodes_positive_and_negative_temperature(driver, raw_bytes, expected):
    module, lgpio = driver
    sensor = module.DHT22(gpio=26)
    checksum = sum(raw_bytes) & 0xFF
    all_bytes = [*raw_bytes, checksum]

    with (
        mock.patch.object(sensor, "_DHT22__send_and_sleep"),
        mock.patch.object(sensor, "_DHT22__collect_input", return_value=[0]),
        mock.patch.object(
            sensor,
            "_DHT22__parse_data_pull_up_lengths",
            return_value=[1] * 40,
        ),
        mock.patch.object(
            sensor,
            "_DHT22__calculate_bits",
            return_value=bits_for_bytes(all_bytes),
        ),
    ):
        temperature, humidity, actual_checksum = sensor.read()

    assert (temperature, humidity) == expected
    assert actual_checksum == checksum
    assert ("output", 99, 26) in lgpio.calls
    assert ("input", 99, 26, lgpio.SET_PULL_UP) in lgpio.calls


def test_read_rejects_missing_bits(driver):
    module, _ = driver
    sensor = module.DHT22(gpio=26)

    with (
        mock.patch.object(sensor, "_DHT22__send_and_sleep"),
        mock.patch.object(sensor, "_DHT22__collect_input", return_value=[0]),
        mock.patch.object(
            sensor,
            "_DHT22__parse_data_pull_up_lengths",
            return_value=[1] * 39,
        ),
        pytest.raises(module.DHT22MissingDataError),
    ):
        sensor.read()


def test_read_rejects_bad_checksum(driver):
    module, _ = driver
    sensor = module.DHT22(gpio=26)
    invalid_bytes = [0x02, 0x30, 0x00, 0xF5, 0x00]

    with (
        mock.patch.object(sensor, "_DHT22__send_and_sleep"),
        mock.patch.object(sensor, "_DHT22__collect_input", return_value=[0]),
        mock.patch.object(
            sensor,
            "_DHT22__parse_data_pull_up_lengths",
            return_value=[1] * 40,
        ),
        mock.patch.object(
            sensor,
            "_DHT22__calculate_bits",
            return_value=bits_for_bytes(invalid_bytes),
        ),
        pytest.raises(module.DHT22CRCError),
    ):
        sensor.read()
