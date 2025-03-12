import ok
from loog import log


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

    def __init__(self):
        """Initialize an empty configuration."""
        self.product_name = None
        self.serial_number = None
        self.product_id = None
        self.device_interface = None
        self.device_interface_str = None
        self.wire_width = None
        self.trigger_width = None
        self.pipe_width = None

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
        config = cls()
        config.product_name = device_info.productName
        config.serial_number = device_info.serialNumber
        config.product_id = device_info.productID
        config.device_interface = device_info.deviceInterface
        config.device_interface_str = interface_list[device_info.deviceInterface]
        config.wire_width = device_info.wireWidth
        config.trigger_width = device_info.triggerWidth
        config.pipe_width = device_info.pipeWidth
        return config

    def validate(self) -> None:
        """
        Validate device configuration.

        Checks if the device configuration meets expected requirements
        and logs warnings for any deviations.
        """
        if self.device_interface != ok.OK_INTERFACE_USB3:
            log("Device interface is not USB 3!", level="warning")
        if self.wire_width != 32:
            log("Wire width is not 32!", level="warning")
        if self.trigger_width != 32:
            log("Trigger width is not 32!", level="warning")
        if self.pipe_width != 32:
            log("Pipe width is not 32!", level="warning")
