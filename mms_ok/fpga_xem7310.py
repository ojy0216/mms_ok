from __future__ import annotations

import numpy as np
from loguru import logger

from .diagnostics import log_critical
from .fpga_base import XEM
from .ok_setup import get_ok
from .validation import validate_address, validate_wire_value


class XEM7310(XEM):
    """
    XEM7310 FPGA device implementation.

    Specific implementation for the XEM7310A75/A200 FPGA boards. Provides
    configuration and control for these models, including 8-LED display control.

    Attributes:
        Inherits all attributes from XEM base class

    Example:
        >>> fpga = XEM7310("bitstream.bit")
    """

    def __init__(self, bitstream_path: str) -> None:
        """
        Initialize XEM7310 FPGA device.

        Args:
            bitstream_path (str): Path to the bitstream file (.bit)

        Raises:
            TypeError: If connected device is not a XEM7310A75/A200
            Plus all exceptions from parent class __init__
        """
        super().__init__(bitstream_path=bitstream_path)
        try:
            ok = get_ok()

            target_product_id_list = [
                ok.okCFrontPanel.brdXEM7310A75,
                ok.okCFrontPanel.brdXEM7310A200,
            ]

            if self.config.product_id not in target_product_id_list:
                log_critical("Connected FPGA board is not a XEM7310A75/A200!")
                raise TypeError("Connected FPGA board is not a XEM7310A75/A200!")
        except Exception:
            self.close()
            raise

    def _check_device_settings(self) -> None:
        """No additional settings to check for XEM7310."""
        pass

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        """
        Control the 8 LEDs on the XEM7310 board.

        Args:
            led_value (int): 8-bit value controlling LED states (0-255)
            led_address (int): Wire address for LED control (default: 0x00)

        Raises:
            ValueError: If led_value is outside valid range (0-255)
        """
        validate_address(0x00, 0x1F, led_address)
        validate_wire_value(led_value, 8)  # 8 LEDs on XEM7310

        self._led_used = True
        self._led_address = self._led_address or led_address
        logger.info(
            f"Setting LED value to {led_value} ({np.binary_repr(led_value, width=8)})"
        )

        self.SetWireInValue(self._led_address, led_value, auto_update=True)
