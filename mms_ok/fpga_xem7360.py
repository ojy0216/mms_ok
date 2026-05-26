from __future__ import annotations

import numpy as np
from loguru import logger

from .diagnostics import log_critical
from .fpga_base import XEM
from .ok_setup import get_ok
from .validation import validate_address, validate_wire_value


class XEM7360(XEM):
    """
    XEM7360 FPGA device implementation.

    Specific implementation for the XEM7360K160T FPGA board. Provides configuration
    and control features, including 4-LED display and voltage settings verification.

    Attributes:
        Inherits all attributes from XEM base class

    Example:
        >>> fpga = XEM7360("bitstream.bit")
    """

    def __init__(self, bitstream_path: str) -> None:
        """
        Initialize XEM7360 FPGA device.

        Args:
            bitstream_path (str): Path to the bitstream file (.bit)

        Raises:
            TypeError: If connected device is not a XEM7360K160T
            Plus all exceptions from parent class __init__
        """
        super().__init__(bitstream_path=bitstream_path)
        try:
            ok = get_ok()

            target_product_id = ok.okCFrontPanel.brdXEM7360K160T

            if self.config.product_id != target_product_id:
                log_critical("Connected FPGA board is not a XEM7360K160T!")
                raise TypeError("Connected FPGA board is not a XEM7360K160T!")
        except Exception:
            self.close()
            raise

    def _check_device_settings(self) -> None:
        """
        Check voltage settings for XEM7360.

        Verifies I/O voltage settings for different banks and logs warnings
        if voltages are set below 120mV.
        """
        ok = get_ok()
        device_settings = ok.okCDeviceSettings()

        ok.okCFrontPanel.GetDeviceSettings(self.xem, device_settings)

        try:
            vadj_voltage_dict = {
                f"vadj{i}": device_settings.GetInt(f"XEM7360_VADJ{i}_VOLTAGE") / 100
                for i in range(1, 3 + 1)
            }
            self._vadj_voltage_dict = vadj_voltage_dict

            vadj_modes = device_settings.GetInt("XEM7360_VADJ_MODE")

            vadj_mask = 0b0000_0011
            for i in range(1, 3 + 1):
                vadj_mode = (vadj_modes & vadj_mask) >> (2 * (i - 1))
                if vadj_mode < 2:
                    logger.warning(f"vadj{i} will be set to 1.20 V!")
                    logger.warning(
                        "Please refer to https://docs.opalkelly.com/xem7360/device-settings/"
                    )

                vadj_mask <<= 2
        except Exception as e:
            logger.exception(f"Error getting device settings: {e}")

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        """
        Control the 4 LEDs on the XEM7360 board.

        Args:
            led_value (int): 4-bit value controlling LED states (0-15)
            led_address (int): Wire address for LED control (default: 0x00)

        Raises:
            ValueError: If led_value is outside valid range (0-15)
        """
        validate_address(0x00, 0x1F, led_address)
        validate_wire_value(led_value, 4)  # 4 LEDs on XEM7360

        self._led_used = True
        self._led_address = self._led_address or led_address
        logger.info(
            f"Setting LED value to {led_value} ({np.binary_repr(led_value, width=4)})"
        )

        self.SetWireInValue(self._led_address, led_value, auto_update=True)
