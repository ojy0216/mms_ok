"""Generic best-effort FrontPanel access for unverified Opal Kelly boards."""

from __future__ import annotations

import warnings
from typing import Optional

from .diagnostics import log_critical
from .fpga_base import XEM
from .fpga_products import verified_product_ids


class UnverifiedXEM(XEM):
    """Concrete generic XEM for unverified boards and common FrontPanel APIs."""

    def __init__(
        self,
        bitstream_path: str,
        *,
        serial: Optional[str] = None,
        _expected_product_id: Optional[int] = None,
    ) -> None:
        super().__init__(
            bitstream_path,
            serial=serial,
            _expected_product_id=_expected_product_id,
        )

    def _validate_connected_board(self) -> None:
        if int(self.config.product_id) in verified_product_ids():
            message = (
                "UnverifiedXEM cannot be used for known verified mms_ok boards; "
                "use XEM, XEM7310, or XEM7360 instead."
            )
            log_critical(message)
            raise TypeError(message)

    def _check_device_settings(self) -> None:
        """No board-specific settings are known for unverified hardware."""
        pass

    def _before_configure(self) -> None:
        warnings.warn(
            "Connected Opal Kelly board is unverified and not hardware-validated "
            "by mms_ok; only common FrontPanel APIs are best-effort supported.",
            RuntimeWarning,
            stacklevel=3,
        )

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        raise NotImplementedError(
            "SetLED is unsupported for unverified Opal Kelly boards because "
            "mms_ok has not hardware-validated board-specific LED wiring."
        )
