from __future__ import annotations

import pytest

import mms_ok
from mms_ok import cli
from mms_ok import devices


class FakeDeviceInfo:
    def __init__(self) -> None:
        self.serialNumber = ""
        self.productName = ""
        self.deviceID = ""
        self.productID = 0


class FakeFrontPanel:
    attached = [
        {
            "serial": "SER001",
            "model": "XEM7310-A75",
            "device_id": "left",
            "product_id": 101,
        },
        {
            "serial": "SER002",
            "model": "XEM7360-K160T",
            "device_id": "right",
            "product_id": 202,
        },
    ]

    def __init__(self) -> None:
        self.open = False
        self.serial = None

    def GetDeviceCount(self) -> int:
        return len(self.attached)

    def GetDeviceListSerial(self, index: int) -> str:
        return self.attached[index]["serial"]

    def GetDeviceListModel(self, index: int) -> str:
        return self.attached[index]["model"]

    def OpenBySerial(self, serial: str) -> int:
        self.serial = serial
        self.open = True
        return 0

    def GetDeviceInfo(self, device_info: FakeDeviceInfo) -> None:
        match = next(item for item in self.attached if item["serial"] == self.serial)
        device_info.serialNumber = match["serial"]
        device_info.productName = match["model"]
        device_info.deviceID = match["device_id"]
        device_info.productID = match["product_id"]

    def IsOpen(self) -> bool:
        return self.open

    def Close(self) -> None:
        self.open = False


class FakeOk:
    okCFrontPanel = FakeFrontPanel
    okTDeviceInfo = FakeDeviceInfo


def test_public_list_devices_is_lazy_and_returns_device_fields(monkeypatch):
    monkeypatch.setattr(devices, "import_ok", lambda: FakeOk)

    found = mms_ok.list_devices()

    assert [device.as_dict() for device in found] == [
        {
            "serial": "SER001",
            "model": "XEM7310-A75",
            "device_id": "left",
            "product_id": 101,
        },
        {
            "serial": "SER002",
            "model": "XEM7360-K160T",
            "device_id": "right",
            "product_id": 202,
        },
    ]


def test_list_devices_wraps_sdk_import_failure(monkeypatch):
    def fail_import():
        raise ImportError("no ok")

    monkeypatch.setattr(devices, "import_ok", fail_import)

    with pytest.raises(devices.FrontPanelUnavailableError, match="FrontPanel SDK"):
        devices.list_devices()


def test_devices_cli_prints_required_columns(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_devices",
        lambda: [
            devices.DeviceInfo(
                serial="SER001",
                model="XEM7310-A75",
                device_id="left",
                product_id=101,
            )
        ],
    )

    status = cli.main(["devices"])

    captured = capsys.readouterr()
    assert status == 0
    assert "device_id" in captured.out
    assert "model" in captured.out
    assert "serial" in captured.out
    assert "product_id" not in captured.out
    assert "left" in captured.out
    assert "XEM7310-A75" in captured.out
    assert "SER001" in captured.out
    assert "101" not in captured.out

    device_id_index = captured.out.index("device_id")
    model_index = captured.out.index("model")
    serial_index = captured.out.index("serial")
    assert device_id_index < model_index < serial_index


def test_devices_cli_reports_no_devices(monkeypatch, capsys):
    monkeypatch.setattr(cli, "list_devices", lambda: [])

    status = cli.main(["devices"])

    captured = capsys.readouterr()
    assert status == cli.EXIT_NO_DEVICES
    assert "No Opal Kelly FrontPanel devices found" in captured.out


def test_devices_cli_reports_sdk_unavailable(monkeypatch, capsys):
    def fail_list():
        raise devices.FrontPanelUnavailableError("FrontPanel SDK is not available.")

    monkeypatch.setattr(cli, "list_devices", fail_list)

    status = cli.main(["devices"])

    captured = capsys.readouterr()
    assert status == cli.EXIT_SDK_UNAVAILABLE
    assert "FrontPanel SDK is not available" in captured.out


def test_devices_cli_reports_unexpected_discovery_error(monkeypatch, capsys):
    def fail_list():
        raise devices.DeviceDiscoveryError("Unexpected error while discovering devices")

    monkeypatch.setattr(cli, "list_devices", fail_list)

    status = cli.main(["devices"])

    captured = capsys.readouterr()
    assert status == cli.EXIT_DISCOVERY_ERROR
    assert "Unexpected error while discovering devices" in captured.out
