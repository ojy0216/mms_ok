from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from .ok_setup import get_ok
from .validation import BlockPipeTransportPolicy


def _lookup_label(values, index: int) -> str:
    try:
        return values[index]
    except (IndexError, TypeError):
        return values[0]


@dataclass
class FPGAConfig:
    """
    Configuration class for FPGA devices.

    Stores and validates device-specific configuration parameters.

    Attributes:
        product_name (str): Name of the FPGA product
        serial_number (str): Serial number of the device
        product_id (int): Product ID of the device
        device_interface (int): Interface type (USB2, PCIe, USB3)
        device_interface_str (str): String representation of interface type
        wire_width (int): Bit width of wire endpoints
        trigger_width (int): Bit width of trigger endpoints
        pipe_width (int): Bit width of pipe endpoints
    """

    product_name: str = ""
    serial_number: str = ""
    product_id: int = 0
    device_interface: int = 0
    device_interface_str: str = ""
    max_bt_blocksize: int = -1
    usb_speed: str = ""
    wire_width: int = 0
    trigger_width: int = 0
    pipe_width: int = 0

    @classmethod
    def from_device_info(cls, device_info: ok.okTDeviceInfo) -> "FPGAConfig":
        """
        Create a configuration object from device information.

        Args:
            device_info (ok.okTDeviceInfo): Device information from FrontPanel

        Returns:
            FPGAConfig: Configured instance
        """
        interface_list = ["Unknown", "USB 2", "PCIe", "USB 3"]
        usb_speed_list = ["Unknown", "FULL", "HIGH", "SUPER"]
        return cls(
            product_name=device_info.productName,
            serial_number=device_info.serialNumber,
            product_id=device_info.productID,
            device_interface=device_info.deviceInterface,
            device_interface_str=_lookup_label(
                interface_list, device_info.deviceInterface
            ),
            max_bt_blocksize=BlockPipeTransportPolicy(
                -1,
                usb_speed=device_info.usbSpeed,
                device_interface=device_info.deviceInterface,
            ).device_max_block_size,
            usb_speed=_lookup_label(usb_speed_list, device_info.usbSpeed),
            wire_width=device_info.wireWidth,
            trigger_width=device_info.triggerWidth,
            pipe_width=device_info.pipeWidth,
        )

    def validate(self) -> None:
        """
        Validate device configuration.

        Checks if the device configuration meets expected requirements
        and logs warnings for any deviations.
        """
        ok = get_ok()
        if self.device_interface != ok.OK_INTERFACE_USB3:
            logger.warning("Device interface is not USB 3!")
        if self.wire_width != 32:
            logger.warning("Wire width is not 32!")
        if self.trigger_width != 32:
            logger.warning("Trigger width is not 32!")
        if self.pipe_width != 32:
            logger.warning("Pipe width is not 32!")
