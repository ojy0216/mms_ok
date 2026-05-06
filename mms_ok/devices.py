"""FrontPanel device discovery helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from .ok_setup import import_ok


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
    try:
        if bool(handle.IsOpen()):
            handle.Close()
    except Exception:
        try:
            handle.Close()
        except Exception:
            pass


def _to_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _get_device_info(ok: Any, serial: str, model: str) -> DeviceInfo:
    handle = ok.okCFrontPanel()
    opened = False

    try:
        error_code = handle.OpenBySerial(serial)
        if error_code != 0:
            raise DeviceDiscoveryError(
                "Could not open device with serial {!r} while reading device info "
                "(OpenBySerial returned {}).".format(serial, error_code)
            )
        opened = True

        raw_info = ok.okTDeviceInfo()
        handle.GetDeviceInfo(raw_info)

        return DeviceInfo(
            serial=_to_text(getattr(raw_info, "serialNumber", serial)),
            model=_to_text(getattr(raw_info, "productName", model)),
            device_id=_to_text(getattr(raw_info, "deviceID", "")),
            product_id=int(getattr(raw_info, "productID", 0)),
        )
    finally:
        if opened:
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
        discovery = ok.okCFrontPanel()
        device_count = discovery.GetDeviceCount()
        devices = []

        for index in range(device_count):
            serial = _to_text(discovery.GetDeviceListSerial(index))
            model = _to_text(discovery.GetDeviceListModel(index))
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
