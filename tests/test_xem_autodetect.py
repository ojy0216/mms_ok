from __future__ import annotations

import warnings

import pytest

import mms_ok
from mms_ok import fpga
from mms_ok import fpga_base
from mms_ok import fpga_config
from mms_ok import fpga_factory
from mms_ok import fpga_generic
from mms_ok import fpga_products
from mms_ok import fpga_xem7360
from mms_ok.devices import DeviceInfo
from mms_ok.fpga_base import ProductIDMismatchError


class FakeDeviceInfo:
    def __init__(self) -> None:
        self.productName = ""
        self.serialNumber = ""
        self.productID = 0
        self.deviceInterface = 3
        self.usbSpeed = 3
        self.wireWidth = 32
        self.triggerWidth = 32
        self.pipeWidth = 32


class FakeFrontPanel:
    brdXEM7310A75 = 101
    brdXEM7310A200 = 102
    brdXEM7360K160T = 203

    attached = []
    instances = []
    configure_error = 0
    frontpanel_enabled = True

    def __init__(self) -> None:
        self.open = False
        self.open_serial = None
        self.selected = None
        self.close_calls = 0
        self.configure_calls = []
        FakeFrontPanel.instances.append(self)

    @staticmethod
    def GetAPIVersionString() -> str:
        return "test"

    def OpenBySerial(self, serial: str) -> int:
        self.open_serial = serial
        target_serial = serial or (
            FakeFrontPanel.attached[0]["serial"] if FakeFrontPanel.attached else None
        )
        for device in FakeFrontPanel.attached:
            if device["serial"] == target_serial:
                self.selected = device
                self.open = True
                return int(device.get("open_error", 0))
        return -1

    def GetDeviceInfo(self, device_info: FakeDeviceInfo) -> None:
        if self.selected is None:
            raise RuntimeError("no selected fake device")
        device_info.productName = self.selected.get(
            "open_model", self.selected["model"]
        )
        device_info.serialNumber = self.selected.get(
            "open_serial_number", self.selected["serial"]
        )
        device_info.productID = self.selected.get(
            "open_product_id", self.selected["product_id"]
        )
        device_info.deviceInterface = 3
        device_info.usbSpeed = 3
        device_info.wireWidth = 32
        device_info.triggerWidth = 32
        device_info.pipeWidth = 32

    def ConfigureFPGA(self, bitstream_path: str) -> int:
        self.configure_calls.append(bitstream_path)
        return FakeFrontPanel.configure_error

    def IsFrontPanelEnabled(self) -> bool:
        return FakeFrontPanel.frontpanel_enabled

    def IsOpen(self) -> bool:
        return self.open

    def Close(self) -> None:
        self.close_calls += 1
        self.open = False

    @staticmethod
    def GetDeviceSettings(handle, device_settings) -> None:
        return None

    @staticmethod
    def GetErrorString(error_code: int) -> str:
        return f"mock error {error_code}"


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


@pytest.fixture(autouse=True)
def fake_frontpanel(monkeypatch):
    FakeFrontPanel.attached = []
    FakeFrontPanel.instances = []
    FakeFrontPanel.configure_error = 0
    FakeFrontPanel.frontpanel_enabled = True

    for module in (
        fpga_base,
        fpga_config,
        fpga_products,
        fpga_xem7360,
    ):
        monkeypatch.setattr(module, "get_ok", lambda: FakeOk)

    monkeypatch.setattr(fpga_base, "print_fpga_overview", lambda **kwargs: None)
    monkeypatch.setattr(fpga_factory, "list_devices", discovered_devices)


@pytest.fixture
def bitstream_path(tmp_path):
    path = tmp_path / "design.bit"
    path.write_bytes(b"fake bitstream")
    return str(path)


def add_device(serial: str, model: str, product_id: int, **overrides) -> None:
    device = {
        "serial": serial,
        "model": model,
        "device_id": overrides.pop("device_id", serial.lower()),
        "product_id": product_id,
    }
    device.update(overrides)
    FakeFrontPanel.attached.append(device)


def discovered_devices():
    return [
        DeviceInfo(
            serial=device["serial"],
            model=device["model"],
            device_id=device["device_id"],
            product_id=device.get("discovery_product_id", device["product_id"]),
        )
        for device in FakeFrontPanel.attached
    ]


def test_xem_factory_is_top_level_lazy_public_and_facade_visible():
    assert "XEM" in dir(mms_ok)
    assert fpga.XEM is fpga_base.XEM
    assert fpga.XEMBase is fpga_base.XEM
    assert isinstance(fpga.XEM, type)
    assert issubclass(fpga.XEM7310, fpga.XEM)
    assert issubclass(fpga.XEM7360, fpga.XEM)
    assert issubclass(fpga.UnverifiedXEM, fpga.XEM)
    assert fpga.autodetect_xem is mms_ok.XEM
    assert fpga.UnverifiedXEM is fpga_generic.UnverifiedXEM
    assert fpga.ProductIDMismatchError is ProductIDMismatchError
    assert "UnverifiedXEM" not in dir(mms_ok)


@pytest.mark.parametrize(
    ("product_id", "expected_model"),
    [
        (FakeFrontPanel.brdXEM7310A75, "XEM7310-A75"),
        (FakeFrontPanel.brdXEM7310A200, "XEM7310-A200"),
    ],
)
def test_xem_factory_returns_xem7310_for_verified_7310_products(
    bitstream_path, product_id, expected_model
):
    add_device("SER7310", expected_model, product_id)

    device = mms_ok.XEM(bitstream_path)

    try:
        assert isinstance(device, fpga.XEM)
        assert isinstance(device, fpga.XEM7310)
        assert device.config.product_id == product_id
        assert FakeFrontPanel.instances[0].open_serial == "SER7310"
        assert FakeFrontPanel.instances[0].configure_calls == [bitstream_path]
    finally:
        device.close()


def test_xem_factory_returns_xem7360_for_k160t(bitstream_path):
    add_device("SER7360", "XEM7360-K160T", FakeFrontPanel.brdXEM7360K160T)

    device = mms_ok.XEM(bitstream_path)

    try:
        assert isinstance(device, fpga.XEM7360)
        assert device.config.product_id == FakeFrontPanel.brdXEM7360K160T
        assert device._vadj_voltage_dict == {
            "vadj1": 1.2,
            "vadj2": 1.2,
            "vadj3": 1.2,
        }
    finally:
        device.close()


def test_xem_factory_returns_unverified_for_unknown_product(bitstream_path):
    add_device("SERUNK", "XEM-UNKNOWN", 999)

    with pytest.warns(RuntimeWarning, match="unverified|not hardware"):
        device = mms_ok.XEM(bitstream_path)

    try:
        assert isinstance(device, fpga.UnverifiedXEM)
        assert device.config.product_id == 999
        assert FakeFrontPanel.instances[0].configure_calls == [bitstream_path]
    finally:
        device.close()


def test_unverified_set_led_unsupported_and_does_not_mark_led_used(bitstream_path):
    add_device("SERUNK", "XEM-UNKNOWN", 999)
    with pytest.warns(RuntimeWarning):
        device = mms_ok.XEM(bitstream_path)

    try:
        with pytest.raises(NotImplementedError, match="unsupported.*unverified"):
            device.SetLED(1)
        assert device._led_used is False
    finally:
        device.close()


def test_unverified_warning_as_error_happens_before_open_or_configure(bitstream_path):
    add_device("SERUNK", "XEM-UNKNOWN", 999)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(RuntimeWarning, match="unverified"):
            mms_ok.XEM(bitstream_path)

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


def test_unverified_common_apis_present(bitstream_path):
    add_device("SERUNK", "XEM-UNKNOWN", 999)
    with pytest.warns(RuntimeWarning):
        device = mms_ok.XEM(bitstream_path)

    try:
        for attr in ("wire_ops", "trigger_ops", "pipe_ops", "block_pipe_ops"):
            assert hasattr(device, attr)
        for method in (
            "SetWireInValue",
            "ActivateTriggerIn",
            "ReadFromPipeOut",
            "WriteRegister",
            "reset",
            "close",
        ):
            assert hasattr(device, method)
    finally:
        device.close()


def test_xem_factory_no_devices_raises_clear_error(bitstream_path):
    with pytest.raises(fpga.FPGASelectionError, match="No Opal Kelly"):
        mms_ok.XEM(bitstream_path)

    assert FakeFrontPanel.instances == []


def test_xem_factory_multiple_devices_without_serial_raises(bitstream_path):
    add_device("SER7310", "XEM7310-A75", FakeFrontPanel.brdXEM7310A75)
    add_device("SER7360", "XEM7360-K160T", FakeFrontPanel.brdXEM7360K160T)

    with pytest.raises(fpga.FPGASelectionError, match="Multiple.*serial"):
        mms_ok.XEM(bitstream_path)

    assert FakeFrontPanel.instances == []


def test_xem_factory_with_serial_targets_matching_device(bitstream_path):
    add_device("SER7310", "XEM7310-A75", FakeFrontPanel.brdXEM7310A75)
    add_device("SER7360", "XEM7360-K160T", FakeFrontPanel.brdXEM7360K160T)

    device = mms_ok.XEM(bitstream_path, serial="SER7360")

    try:
        assert isinstance(device, fpga.XEM7360)
        assert FakeFrontPanel.instances[0].open_serial == "SER7360"
    finally:
        device.close()


def test_xem_factory_with_unknown_serial_raises_clear_error(bitstream_path):
    add_device("SER7310", "XEM7310-A75", FakeFrontPanel.brdXEM7310A75)

    with pytest.raises(fpga.FPGASelectionError, match="SER404"):
        mms_ok.XEM(bitstream_path, serial="SER404")

    assert FakeFrontPanel.instances == []


@pytest.mark.parametrize(
    ("discovery_product_id", "open_product_id"),
    [
        (FakeFrontPanel.brdXEM7310A75, FakeFrontPanel.brdXEM7310A200),
        (900, 901),
    ],
)
def test_xem_factory_exact_product_change_fails_before_configure(
    bitstream_path, discovery_product_id, open_product_id
):
    add_device(
        "SERCHANGE",
        "XEM-CHANGED",
        open_product_id,
        discovery_product_id=discovery_product_id,
    )

    with pytest.raises(ProductIDMismatchError, match="changed before configuration"):
        mms_ok.XEM(bitstream_path)

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


def test_xem_factory_serial_change_fails_before_configure(bitstream_path):
    add_device(
        "SERCHANGE",
        "XEM7310-A75",
        FakeFrontPanel.brdXEM7310A75,
        open_serial_number="SEROTHER",
    )

    with pytest.raises(ProductIDMismatchError, match="serial changed"):
        mms_ok.XEM(bitstream_path)

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


def test_xem_factory_blank_opened_serial_fails_before_configure(bitstream_path):
    add_device(
        "SERCHANGE",
        "XEM7310-A75",
        FakeFrontPanel.brdXEM7310A75,
        open_serial_number="",
    )

    with pytest.raises(ProductIDMismatchError, match="serial changed"):
        mms_ok.XEM(bitstream_path)

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


def test_missing_required_product_id_constant_fails_clearly(monkeypatch, bitstream_path):
    class MissingProductConstantOk:
        class okCFrontPanel:
            brdXEM7310A75 = FakeFrontPanel.brdXEM7310A75
            brdXEM7310A200 = FakeFrontPanel.brdXEM7310A200

    monkeypatch.setattr(fpga_products, "get_ok", lambda: MissingProductConstantOk)
    add_device("SERUNK", "XEM-UNKNOWN", 999)

    with pytest.raises(AttributeError, match="brdXEM7360K160T"):
        mms_ok.XEM(bitstream_path)

    assert FakeFrontPanel.instances == []


def test_constructor_serial_keyword_only_and_records_serial(bitstream_path):
    add_device("SER7310", "XEM7310-A75", FakeFrontPanel.brdXEM7310A75)

    with pytest.raises(TypeError):
        fpga.XEM7310(bitstream_path, "SER7310")

    device = fpga.XEM7310(bitstream_path, serial="SER7310")
    try:
        assert FakeFrontPanel.instances[0].open_serial == "SER7310"
    finally:
        device.close()


def test_verified_constructors_with_serial_remain_strict(bitstream_path):
    add_device("SERUNK", "XEM-UNKNOWN", 999)

    with pytest.raises(TypeError, match="XEM7310A75/A200"):
        fpga.XEM7310(bitstream_path, serial="SERUNK")

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []

    FakeFrontPanel.instances = []
    FakeFrontPanel.attached = []
    add_device("SER7310", "XEM7310-A75", FakeFrontPanel.brdXEM7310A75)

    with pytest.raises(TypeError, match="XEM7360K160T"):
        fpga.XEM7360(bitstream_path, serial="SER7310")

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []


def test_unverified_direct_constructor_rejects_verified_boards_before_configure(
    bitstream_path,
):
    add_device("SER7310", "XEM7310-A75", FakeFrontPanel.brdXEM7310A75)

    with pytest.raises(TypeError, match="known verified"):
        fpga.UnverifiedXEM(bitstream_path, serial="SER7310")

    handle = FakeFrontPanel.instances[0]
    assert handle.close_calls == 1
    assert handle.configure_calls == []
