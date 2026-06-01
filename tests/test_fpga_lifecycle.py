from __future__ import annotations

import weakref
from io import StringIO

import pytest
from rich.console import Console

from mms_ok import fpga
from mms_ok import fpga_base
from mms_ok import fpga_config
from mms_ok import fpga_xem7310
from mms_ok import fpga_xem7360


class FakeDeviceInfo:
    def __init__(self) -> None:
        self.productName = FakeFrontPanel.product_name
        self.serialNumber = "1234"
        self.productID = FakeFrontPanel.product_id
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
    product_name = "XEM7310"
    product_id = brdXEM7310A75

    def __init__(self) -> None:
        self.open = False
        self.close_calls = 0
        self.configure_calls = []
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
        self.configure_calls.append(bitstream_path)
        return FakeFrontPanel.configure_error

    def IsFrontPanelEnabled(self) -> bool:
        return FakeFrontPanel.frontpanel_enabled

    def IsOpen(self) -> bool:
        self.is_open_calls += 1
        return self.open

    def Close(self) -> None:
        self.close_calls += 1
        self.open = False

    @staticmethod
    def GetDeviceSettings(handle, device_settings) -> None:
        return None


class FakeDeviceSettings:
    def GetInt(self, key: str) -> int:
        values = {
            "XEM7360_VADJ1_VOLTAGE": 120,
            "XEM7360_VADJ2_VOLTAGE": 120,
            "XEM7360_VADJ3_VOLTAGE": 120,
            "XEM7360_VADJ_MODE": 0b0010_1010,
        }
        return values[key]


class FakeOk:
    OK_INTERFACE_USB3 = 3
    okCFrontPanel = FakeFrontPanel
    okTDeviceInfo = FakeDeviceInfo
    okCDeviceSettings = FakeDeviceSettings


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
    FakeFrontPanel.product_name = "XEM7310"
    FakeFrontPanel.product_id = FakeFrontPanel.brdXEM7310A75
    LifecycleXEM.check_error = None

    monkeypatch.setattr(fpga_base, "get_ok", lambda: FakeOk)
    monkeypatch.setattr(fpga_config, "get_ok", lambda: FakeOk)
    monkeypatch.setattr(fpga_base, "print_fpga_overview", lambda **kwargs: None)


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


def test_xem7310_constructor_uses_board_module_get_ok(monkeypatch, bitstream_path):
    monkeypatch.setattr(fpga_xem7310, "get_ok", lambda: FakeOk)

    device = fpga.XEM7310(bitstream_path)

    try:
        assert isinstance(device, fpga.XEM)
        assert device.config.product_id == FakeFrontPanel.brdXEM7310A75
        assert device.is_open() is True
        assert FakeFrontPanel.instances[0].configure_calls == [bitstream_path]
    finally:
        device.close()


def test_xem7360_constructor_uses_board_module_get_ok(monkeypatch, bitstream_path):
    FakeFrontPanel.product_name = "XEM7360"
    FakeFrontPanel.product_id = FakeFrontPanel.brdXEM7360K160T
    monkeypatch.setattr(fpga_xem7360, "get_ok", lambda: FakeOk)

    device = fpga.XEM7360(bitstream_path)

    try:
        assert isinstance(device, fpga.XEM)
        assert device.config.product_id == FakeFrontPanel.brdXEM7360K160T
        assert device._vadj_voltage_dict == {
            "vadj1": 1.2,
            "vadj2": 1.2,
            "vadj3": 1.2,
        }
        assert device.is_open() is True
        assert FakeFrontPanel.instances[0].configure_calls == [bitstream_path]
    finally:
        device.close()


def test_xem7310_wrong_board_fails_before_configure(monkeypatch, bitstream_path):
    FakeFrontPanel.product_name = "XEM7360"
    FakeFrontPanel.product_id = FakeFrontPanel.brdXEM7360K160T
    monkeypatch.setattr(fpga_xem7310, "get_ok", lambda: FakeOk)

    with pytest.raises(TypeError, match="XEM7310A75/A200"):
        fpga.XEM7310(bitstream_path)

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


def test_xem7360_wrong_board_fails_before_configure(monkeypatch, bitstream_path):
    FakeFrontPanel.product_name = "XEM7310"
    FakeFrontPanel.product_id = FakeFrontPanel.brdXEM7310A75
    monkeypatch.setattr(fpga_xem7360, "get_ok", lambda: FakeOk)

    with pytest.raises(TypeError, match="XEM7360K160T"):
        fpga.XEM7360(bitstream_path)

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


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


def test_relative_bitstream_path_is_parent_bitstreams_relative(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    bitstream_dir = tmp_path / "bitstreams"
    work_dir.mkdir()
    bitstream_dir.mkdir()
    path = bitstream_dir / "design.bit"
    path.write_bytes(b"fake bitstream")
    monkeypatch.chdir(work_dir)

    device = LifecycleXEM("design.bit")

    try:
        assert device._bitstream_path == str(path.resolve())
    finally:
        device.close()


def test_directory_relative_bitstream_path_is_cwd_relative(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    cwd_bitstream_dir = work_dir / "path" / "to"
    parent_bitstream_dir = tmp_path / "bitstreams" / "path" / "to"
    cwd_bitstream_dir.mkdir(parents=True)
    parent_bitstream_dir.mkdir(parents=True)
    cwd_path = cwd_bitstream_dir / "design.bit"
    parent_path = parent_bitstream_dir / "design.bit"
    cwd_path.write_bytes(b"fake cwd bitstream")
    parent_path.write_bytes(b"fake parent bitstream")
    monkeypatch.chdir(work_dir)

    device = LifecycleXEM("path/to/design.bit")

    try:
        assert device._bitstream_path == str(cwd_path.resolve())
    finally:
        device.close()


def test_absolute_bitstream_path_is_used_directly(tmp_path):
    path = tmp_path / "design.bit"
    path.write_bytes(b"fake bitstream")

    device = LifecycleXEM(str(path))

    try:
        assert device._bitstream_path == str(path.resolve())
    finally:
        device.close()


def test_filename_bitstream_ignores_cwd_file_and_uses_parent_bitstreams(
    tmp_path, monkeypatch
):
    work_dir = tmp_path / "work"
    bitstream_dir = tmp_path / "bitstreams"
    work_dir.mkdir()
    bitstream_dir.mkdir()
    cwd_path = work_dir / "design.bit"
    parent_path = bitstream_dir / "design.bit"
    cwd_path.write_bytes(b"fake cwd bitstream")
    parent_path.write_bytes(b"fake parent bitstream")
    monkeypatch.chdir(work_dir)

    device = LifecycleXEM("design.bit")

    try:
        assert device._bitstream_path == str(parent_path.resolve())
    finally:
        device.close()


def test_missing_filename_bitstream_reports_checked_parent_bitstreams_path(
    tmp_path, monkeypatch
):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    missing = tmp_path / "bitstreams" / "missing.bit"
    monkeypatch.chdir(work_dir)

    with pytest.raises(FileNotFoundError) as exc_info:
        LifecycleXEM("missing.bit")

    message = str(exc_info.value)
    assert "../bitstreams" in message
    assert str(missing.resolve()) in message


def test_diagnostics_returns_required_keys(bitstream_path):
    device = LifecycleXEM(bitstream_path)

    try:
        data = device.diagnostics(print_output=False)
    finally:
        device.close()

    assert data["board"]["product_name"] == "XEM7310"
    assert data["frontpanel"]["version"] == "test"
    assert data["frontpanel"]["is_open"] is True
    assert data["bitstream"]["path"] == bitstream_path
    assert data["endpoints"]["trigger"]["width"] == 32
    assert data["endpoints"]["block_pipe"]["max_block_size"] == 16384


def test_diagnostics_prints_rich_panel(bitstream_path):
    device = LifecycleXEM(bitstream_path)
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=120)

    try:
        data = device.diagnostics(console=console)
    finally:
        device.close()

    output = stream.getvalue()
    assert data["frontpanel"]["is_open"] is True
    assert "FPGA Diagnostics" in output
    assert "Endpoints" in output
    assert "Bitstream path" in output
