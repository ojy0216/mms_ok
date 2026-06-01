from __future__ import annotations

import pytest

from mms_ok import fpga_base


class PollingXEM(fpga_base.XEM):
    def _check_device_settings(self) -> None:
        return None

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        return None


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps = []

    def perf_counter(self) -> float:
        return self.current

    def sleep(self, duration: float) -> None:
        self.sleeps.append(duration)
        self.current += duration


def make_device() -> PollingXEM:
    device = object.__new__(PollingXEM)
    device.verbose_level = 0
    device.trigger_poll_interval = 0.001
    return device


def test_check_triggered_sleeps_between_failed_checks(monkeypatch):
    device = make_device()
    clock = FakeClock()
    trigger_calls = 0

    def is_triggered(ep_addr, mask, auto_update=False):
        nonlocal trigger_calls
        trigger_calls += 1
        return False

    monkeypatch.setattr(device, "IsTriggered", is_triggered)
    monkeypatch.setattr(fpga_base.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(fpga_base.time, "sleep", clock.sleep)

    with pytest.raises(TimeoutError):
        device.CheckTriggered(0x60, 0x01, timeout=0.003)

    assert clock.sleeps == pytest.approx([0.001, 0.001, 0.001])
    assert trigger_calls == 4


def test_check_triggered_uses_per_call_poll_interval(monkeypatch):
    device = make_device()
    device.trigger_poll_interval = 0.25
    clock = FakeClock()

    monkeypatch.setattr(
        device,
        "IsTriggered",
        lambda ep_addr, mask, auto_update=False: False,
    )
    monkeypatch.setattr(fpga_base.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(fpga_base.time, "sleep", clock.sleep)

    with pytest.raises(TimeoutError):
        device.CheckTriggered(0x60, 0x01, timeout=0.005, poll_interval=0.002)

    assert clock.sleeps == pytest.approx([0.002, 0.002, 0.001])


def test_check_triggered_poll_interval_zero_does_not_sleep(monkeypatch):
    device = make_device()
    trigger_results = iter([False, True])

    monkeypatch.setattr(
        device,
        "IsTriggered",
        lambda ep_addr, mask, auto_update=False: next(trigger_results),
    )
    monkeypatch.setattr(fpga_base.time, "sleep", lambda duration: pytest.fail("slept"))

    device.CheckTriggered(0x60, 0x01, timeout=1.0, poll_interval=0)


def test_check_triggered_negative_poll_interval_raises_value_error():
    device = make_device()

    with pytest.raises(ValueError, match="poll_interval must be non-negative"):
        device.CheckTriggered(0x60, 0x01, poll_interval=-0.001)


def test_check_triggered_timeout_still_raises(monkeypatch):
    device = make_device()
    clock = FakeClock()

    monkeypatch.setattr(
        device,
        "IsTriggered",
        lambda ep_addr, mask, auto_update=False: False,
    )
    monkeypatch.setattr(fpga_base.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(fpga_base.time, "sleep", clock.sleep)

    with pytest.raises(TimeoutError, match="condition not met within timeout"):
        device.CheckTriggered(0x60, 0x01, timeout=0.001)
