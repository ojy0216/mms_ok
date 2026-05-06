from __future__ import annotations

import weakref

import pytest

from mms_ok import fpga
from mms_ok import fpga_config


class FakeDeviceInfo:
    def __init__(self) -> None:
        self.productName = "XEM7310"
        self.serialNumber = "1234"
        self.productID = FakeFrontPanel.brdXEM7310A75
        self.deviceInterface = 3
        self.usbSpeed = 3
        self.wireWidth = 32
        self.triggerWidth = 32
        self.pipeWidth = 32


class FakeFrontPanel:
    brdXEM7310A75 = 1
    brdXEM7310A200 = 2
    brdXEM7360K160T = 3

    instances = []
    open_error = 0
    configure_error = 0
    frontpanel_enabled = True

    def __init__(self) -> None:
        self.open = False
        self.close_calls = 0
        self.is_open_calls = 0
        FakeFrontPanel.instances.append(self)

    @staticmethod
    def GetAPIVersionString() -> str:
        return "test"

    def OpenBySerial(self, serial: str) -> int:
        if FakeFrontPanel.open_error:
            return FakeFrontPanel.open_error
        self.open = True
        return 0

    def GetDeviceInfo(self, device_info: FakeDeviceInfo) -> None:
        return None

    def ConfigureFPGA(self, bitstream_path: str) -> int:
        return FakeFrontPanel.configure_error

    def IsFrontPanelEnabled(self) -> bool:
        return FakeFrontPanel.frontpanel_enabled

    def IsOpen(self) -> bool:
        self.is_open_calls += 1
        return self.open

    def Close(self) -> None:
        self.close_calls += 1
        self.open = False


class FakeOk:
    OK_INTERFACE_USB3 = 3
    okCFrontPanel = FakeFrontPanel
    okTDeviceInfo = FakeDeviceInfo


class LifecycleXEM(fpga.XEM):
    check_error = None

    def _check_device_settings(self) -> None:
        if self.check_error is not None:
            raise self.check_error

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        self._led_used = True
        self._led_address = led_address


@pytest.fixture(autouse=True)
def fake_frontpanel(monkeypatch):
    FakeFrontPanel.instances = []
    FakeFrontPanel.open_error = 0
    FakeFrontPanel.configure_error = 0
    FakeFrontPanel.frontpanel_enabled = True
    LifecycleXEM.check_error = None

    monkeypatch.setattr(fpga, "get_ok", lambda: FakeOk)
    monkeypatch.setattr(fpga_config, "get_ok", lambda: FakeOk)
    monkeypatch.setattr(fpga, "print_fpga_overview", lambda **kwargs: None)


@pytest.fixture
def bitstream_path(tmp_path):
    path = tmp_path / "test.bit"
    path.write_bytes(b"fake bitstream")
    return str(path)


def make_uninitialized_device(handle: FakeFrontPanel) -> LifecycleXEM:
    device = object.__new__(LifecycleXEM)
    device.xem = handle
    device._opened = handle.open
    device._led_used = False
    device._led_address = None
    device._close_finalizer = weakref.finalize(
        device, fpga.XEM._finalize_xem_handle, handle
    )
    return device


def test_is_open_delegates_to_frontpanel_is_open():
    handle = FakeFrontPanel()
    handle.open = True
    device = make_uninitialized_device(handle)

    assert device.is_open() is True
    assert handle.is_open_calls == 1

    device.close()


def test_close_calls_close_once_when_open():
    handle = FakeFrontPanel()
    handle.open = True
    device = make_uninitialized_device(handle)

    device.close()

    assert handle.close_calls == 1
    assert handle.open is False


def test_close_twice_is_noop_on_second_call():
    handle = FakeFrontPanel()
    handle.open = True
    device = make_uninitialized_device(handle)

    device.close()
    device.close()

    assert handle.close_calls == 1


def test_exit_uses_idempotent_close_path():
    handle = FakeFrontPanel()
    handle.open = True
    device = make_uninitialized_device(handle)

    device.__exit__(None, None, None)
    device.__exit__(None, None, None)

    assert handle.close_calls == 1


def test_explicit_close_detaches_fallback_finalizer():
    handle = FakeFrontPanel()
    handle.open = True
    device = make_uninitialized_device(handle)
    finalizer = device._close_finalizer

    device.close()
    finalizer()

    assert finalizer.alive is False
    assert handle.close_calls == 1


def test_configure_failure_after_open_closes_handle(bitstream_path):
    FakeFrontPanel.configure_error = -1

    with pytest.raises(RuntimeError):
        LifecycleXEM(bitstream_path)

    assert FakeFrontPanel.instances[0].close_calls == 1


def test_check_device_settings_failure_after_configure_closes_handle(bitstream_path):
    LifecycleXEM.check_error = RuntimeError("settings failed")

    with pytest.raises(RuntimeError, match="settings failed"):
        LifecycleXEM(bitstream_path)

    assert FakeFrontPanel.instances[0].close_calls == 1


def test_open_failure_does_not_close_unopened_handle(bitstream_path):
    FakeFrontPanel.open_error = -1

    with pytest.raises(ConnectionError):
        LifecycleXEM(bitstream_path)

    assert FakeFrontPanel.instances[0].close_calls == 0
