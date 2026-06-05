"""Discovery-backed FPGA factory."""

from __future__ import annotations

from typing import Optional, Type

from .devices import DeviceInfo, list_devices
from .fpga_base import XEM as XEMBase
from .fpga_generic import UnverifiedXEM
from .fpga_products import xem7310_product_ids, xem7360_product_ids
from .fpga_xem7310 import XEM7310
from .fpga_xem7360 import XEM7360


class FPGASelectionError(RuntimeError):
    """Raised when autodetect cannot select exactly one FrontPanel device."""


def _device_summary(device: DeviceInfo) -> str:
    return (
        "serial={serial!r}, model={model!r}, device_id={device_id!r}, "
        "product_id={product_id}"
    ).format(**device.as_dict())


def _select_device(serial: Optional[str]) -> DeviceInfo:
    devices = list_devices()

    if serial is not None:
        serial_text = str(serial)
        for device in devices:
            if device.serial == serial_text:
                return device
        available = "; ".join(_device_summary(device) for device in devices) or "none"
        raise FPGASelectionError(
            "No Opal Kelly FrontPanel device with serial {!r} was found. "
            "Available devices: {}".format(serial_text, available)
        )

    if not devices:
        raise FPGASelectionError("No Opal Kelly FrontPanel devices were found.")

    if len(devices) > 1:
        available = "; ".join(_device_summary(device) for device in devices)
        raise FPGASelectionError(
            "Multiple Opal Kelly FrontPanel devices were found; pass serial=... "
            "to XEM. Available devices: {}".format(available)
        )

    return devices[0]


def _class_for_product_id(product_id: int) -> Type[XEMBase]:
    if int(product_id) in xem7310_product_ids():
        return XEM7310
    if int(product_id) in xem7360_product_ids():
        return XEM7360
    return UnverifiedXEM


def XEM(bitstream_path: str, serial: Optional[str] = None) -> XEMBase:
    """Open a discovered Opal Kelly FPGA as the best matching mms_ok class."""
    device = _select_device(serial)
    device_class = _class_for_product_id(device.product_id)
    return device_class(
        bitstream_path,
        serial=device.serial,
        _expected_product_id=device.product_id,
    )
