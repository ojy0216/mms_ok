"""FrontPanel device discovery helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from .ok_setup import import_ok
from ._frontpanel_compat import (
    close_device,
    device_serials,
    open_device,
    read_device_info,
    to_text,
)


class FrontPanelUnavailableError(RuntimeError):
    """Raised when the FrontPanel SDK cannot be imported."""


class DeviceDiscoveryError(RuntimeError):
    """Raised when device enumeration fails unexpectedly."""


@dataclass(frozen=True)
class DeviceInfo:
    """Public representation of an attached FrontPanel device."""

    serial: str
    model: str
    device_id: str
    product_id: int

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _close_frontpanel(handle: Any) -> None:
    close_device(handle)


def _to_text(value: Any) -> str:
    return to_text(value)


def _get_device_info(ok: Any, serial: str, model: str) -> DeviceInfo:
    handle = None
    try:
        handle = open_device(ok, serial)
        raw_info = read_device_info(ok, handle)
        actual_serial = _to_text(getattr(raw_info, "serialNumber", serial))
        if actual_serial != serial:
            raise DeviceDiscoveryError(
                "Device serial changed while reading device info: {!r} != {!r}".format(
                    actual_serial, serial
                )
            )

        return DeviceInfo(
            serial=_to_text(getattr(raw_info, "serialNumber", serial)),
            model=_to_text(getattr(raw_info, "productName", model)),
            device_id=_to_text(getattr(raw_info, "deviceID", "")),
            product_id=int(getattr(raw_info, "productID", 0)),
        )
    finally:
        _close_frontpanel(handle)


def list_devices() -> List[DeviceInfo]:
    """Return attached Opal Kelly devices.

    The FrontPanel SDK import is intentionally lazy so ``import mms_ok`` remains
    usable on machines where the SDK is not installed.
    """

    try:
        ok = import_ok()
    except ImportError as exc:
        raise FrontPanelUnavailableError(
            "FrontPanel SDK is not available. Run `mms_ok check-sdk` or "
            "`mms_ok setup-frontpanel` to diagnose the SDK installation."
        ) from exc

    try:
        devices = []
        for serial, model in device_serials(ok):
            devices.append(_get_device_info(ok, serial, model))

        return devices
    except DeviceDiscoveryError:
        raise
    except Exception as exc:
        raise DeviceDiscoveryError(
            "Unexpected error while discovering FrontPanel devices: {}: {}".format(
                type(exc).__name__, exc
            )
        ) from exc
