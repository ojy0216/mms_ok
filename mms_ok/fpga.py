import datetime
import os
import time
import types
from abc import ABC, abstractmethod
from typing import Optional, Type, Union

import numpy as np
import ok
from loguru import logger

from .fpga_components import (
    BlockPipeOperations,
    PipeOperations,
    TriggerOperations,
    WireOperations,
)
from .fpga_config import FPGAConfig
from .pipeoutdata import PipeOutData
from .validation import validate_address, validate_wire_value


class XEM(ABC):
    """
    Abstract base class for Opal Kelly FPGA devices.

    This class provides a common interface for different FPGA models, implementing core
    functionality for device communication and management. It handles device initialization,
    configuration, and provides methods for wire, trigger, and pipe operations.

    Attributes:
        xem (ok.okCFrontPanel): Low-level interface to the FPGA device
        config (FPGAConfig): Device-specific configuration parameters
        wire_ops (WireOperations): Interface for wire-based I/O operations
        trigger_ops (TriggerOperations): Interface for trigger-based operations
        pipe_ops (PipeOperations): Interface for pipe data transfer operations
        block_pipe_ops (BlockPipeOperations): Interface for block pipe data transfers

    Example:
        >>> with XEM7310("path/to/bitstream.bit") as fpga:
        ...     fpga.SetLED(4, 0xFF)  # Turn on all LEDs
        ...     fpga.reset()        # Reset the device
    """

    def __init__(self, bitstream_path: str) -> None:
        """
        Initialize and configure the FPGA device.

        Performs device connection, bitstream loading, and component initialization.
        Sets up operation interfaces for wires, triggers, and pipes.

        Args:
            bitstream_path (str): Path to the bitstream file (.bit)

        Raises:
            FileNotFoundError: If bitstream file doesn't exist
            ValueError: If bitstream file extension is not .bit
            ConnectionError: If device connection fails
            RuntimeError: If bitstream loading or FrontPanel initialization fails
        """
        self._led_used = False
        self._led_address = None
        self.xem = ok.okCFrontPanel()

        self._bitstream_path = os.path.abspath(bitstream_path)
        self._validate_bitstream_path()

        self._connect()
        self._configure()

        self.auto_wire_in = True
        self.auto_wire_out = True
        self.auto_trigger_out = True

        # Initialize components
        self.wire_ops = WireOperations(self.xem, self.config.wire_width)
        self.trigger_ops = TriggerOperations(self.xem, self.config.trigger_width)
        self.pipe_ops = PipeOperations(self.xem)
        self.block_pipe_ops = BlockPipeOperations(
            self.xem, self.config.max_bt_blocksize
        )

        self._check_device_settings()

        logger.info(f"AutoWireIn is {'enabled' if self.auto_wire_in else 'disabled'}!")
        logger.info(
            f"AutoWireOut is {'enabled' if self.auto_wire_out else 'disabled'}!"
        )
        logger.info(
            f"AutoTriggerOut is {'enabled' if self.auto_trigger_out else 'disabled'}!"
        )
        logger.info("FPGA initialized!\n")

    def _validate_bitstream_path(self) -> None:
        """
        Validates the bitstream path and checks if it is a valid bitstream file.

        Args:
            None

        Returns:
            None

        Raises:
            FileNotFoundError: If the bitstream path is invalid.
            ValueError: If the bitstream file extension is not ".bit".
        """
        if not os.path.isfile(self._bitstream_path):
            logger.critical(f'"{self._bitstream_path}" is invalid!')
            raise FileNotFoundError(f"{self._bitstream_path} is an invalid bitstream!")

        extension = os.path.splitext(self._bitstream_path)[1]
        if extension != ".bit":
            logger.critical(f"{extension} is not a valid bitstream file extension!")
            raise ValueError(f"{extension} is not a valid bitstream file extension!")

        logger.info(f"Bitstream file: {self._bitstream_path}")

        timestamp = os.path.getmtime(self._bitstream_path)
        logger.info(
            f"Bitstream date: {datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}",
        )

    def _connect(self) -> None:
        """
        Connects to the FPGA device.

        Args:
            None

        Returns:
            None

        Raises:
            ConnectionError: If the device fails to open.
        """
        if self.xem.OpenBySerial(""):
            logger.critical("Device is not opened!")
            raise ConnectionError("Device is not opened!")

        device_info = ok.okTDeviceInfo()
        self.xem.GetDeviceInfo(device_info)

        self.config = FPGAConfig.from_device_info(device_info)
        self.config.validate()

        logger.info(f"Model        : {self.config.product_name}")
        logger.info(f"Serial Number: {self.config.serial_number}")
        logger.info(f"Interface    : {self.config.device_interface_str}")
        logger.info(f"USB Speed    : {self.config.usb_speed}")
        logger.info(f"Max Blocksize: {self.config.max_bt_blocksize}")
        logger.info(f"Wire Width   : {self.config.wire_width}")
        logger.info(f"Trigger Width: {self.config.trigger_width}")
        logger.info(f"Pipe Width   : {self.config.pipe_width}")

    def _configure(self) -> None:
        """
        Configures the FPGA with the specified bitstream file.

        Args:
            None

        Returns:
            None

        Raises:
            RuntimeError: If the bitstream file is not connected to the device or if FrontPanel is not enabled.
        """
        error_code = self.xem.ConfigureFPGA(self._bitstream_path)
        bitstream_name = os.path.basename(self._bitstream_path)
        if error_code == 0:
            logger.info(
                f'Input bitstream file: "{bitstream_name}" is connected to the device!',
            )
        else:
            logger.critical(
                f'Input bitstream file: "{bitstream_name}" is not connected to the device!',
            )
            raise RuntimeError(
                f'Input bitstream file: "{bitstream_name}" is not connected to the device!'
            )

        if self.xem.IsFrontPanelEnabled():
            logger.info("FrontPanel is enabled!")
        else:
            logger.critical("FrontPanel is not enabled!")
            raise RuntimeError("FrontPanel is not enabled!")

    @abstractmethod
    def _check_device_settings(self) -> None:
        """
        Check device-specific settings.

        This method should be implemented by subclasses to verify
        model-specific configurations and requirements.
        """
        pass

    def __enter__(self) -> "XEM":
        """
        Enter method for context manager.

        This method is called when entering a `with` statement. It returns the context manager object itself.

        Args:
            None

        Returns:
            self: The context manager object itself.
        """
        return self

    def close(self) -> None:
        """
        Close the FPGA device.
        """
        self.__exit__(None, None, None)

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> None:
        """
        Exit the context manager and perform necessary cleanup operations.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of the exception raised, if any.
            exc_val (Optional[BaseException]): The exception raised, if any.
            exc_tb (Optional[types.TracebackType]): The traceback object associated with the exception, if any.

        Returns:
            None
        """
        logger.info("Closing device")
        if self._led_used:
            logger.info("Turning off the LEDs before closing the device!")
            self.SetLED(led_value=0, led_address=self._led_address)
        self.xem.Close()
        logger.info("Device closed!")

    def reset(
        self, reset_address: int = 0x00, reset_time: float = 1.0, active_low=True
    ) -> None:
        """
        Reset the FPGA device using a wire signal.

        Sends a reset signal to the specified wire address for the given duration.
        The reset signal can be either active-low or active-high.

        Args:
            reset_address (int): Wire address for reset signal (0x00 - 0x1F)
            reset_time (float): Duration to hold reset signal active, in seconds (default: 1)
            active_low (bool): If True, reset is active when signal is low (default: True)

        Raises:
            ValueError: If reset_address is not in range 0x00 - 0x1F
        """
        validate_address(0x00, 0x1F, reset_address)

        reset_value, nominal_value = (0, 1) if active_low else (1, 0)

        logger.info(f"Reset Start ({reset_time}s)")
        self.SetWireInValue(reset_address, reset_value)
        self.UpdateWireIns()

        time.sleep(reset_time)

        self.SetWireInValue(reset_address, nominal_value)
        self.UpdateWireIns()
        logger.info(f"Reset End ({reset_time}s)\n")

    @abstractmethod
    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        """
        Set LED values on the FPGA board.

        Args:
            led_value (int): Value to set (must be representable with num_leds bits)
            led_address (int): Wire address for LED control. Defaults to 0x00

        Raises:
            ValueError: If led_value cannot be represented with num_leds bits
            ValueError: If led_address is not in range 0x00 - 0x1F
        """
        pass

    def SetAutoWireIn(self, auto_update: bool) -> None:
        """
        Enable automatic update of wire-in values.

        Args:
            auto_update (bool): If True, automatically update wire-in values after setting
        """
        self.auto_wire_in = auto_update
        logger.info(f"AutoWireIn is {'enabled' if auto_update else 'disabled'}!")

    def SetAutoWireOut(self, auto_update: bool) -> None:
        """
        Enable automatic update of wire-out values.

        Args:
            auto_update (bool): If True, automatically update wire-out values after setting
        """
        self.auto_wire_out = auto_update
        logger.info(f"AutoWireOut is {'enabled' if auto_update else 'disabled'}!")

    def SetAutoTriggerOut(self, auto_update: bool) -> None:
        """
        Enable automatic update of trigger-out values.

        Args:
            auto_update (bool): If True, automatically update trigger-out values after setting
        """
        self.auto_trigger_out = auto_update
        logger.info(f"AutoTriggerOut is {'enabled' if auto_update else 'disabled'}!")

    def SetWireInValue(
        self,
        ep_addr: int,
        value: int,
        mask: Optional[int] = None,
        auto_update: bool = False,
    ) -> int:
        """
        Set a value to be written to a wire-in endpoint.

        Args:
            ep_addr (int): Wire endpoint address (0x00 - 0x1F)
            value (int): Value to write
            mask (Optional[int]): Bit mask to apply to value (default: None)
            auto_update (bool): If True, automatically update wire-in values after setting (default: False)

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.wire_ops.set_wire_in(ep_addr, value, mask)
        if self.auto_wire_in or auto_update:
            self.UpdateWireIns()
        return error_code

    def UpdateWireIns(self) -> int:
        """
        Update all wire-in endpoints.

        Transfers all wire-in values that have been set using SetWireInValue()
        to the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        return self.wire_ops.update_wire_ins()

    def UpdateWireOuts(self) -> int:
        """
        Update all wire-out endpoints.

        Reads the current state of all wire-out endpoints from the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        return self.wire_ops.update_wire_outs()

    def GetWireOutValue(self, ep_addr: int, auto_update: bool = False) -> int:
        """
        Get the value of a wire-out endpoint.

        Args:
            ep_addr (int): Wire endpoint address (0x00 - 0x1F)
            auto_update (bool): If True, automatically update wire-out values before reading (default: False)

        Returns:
            int: Current value of the specified wire-out endpoint

        Note:
            UpdateWireOuts() must be called before this method to get current values.
        """
        if self.auto_wire_out or auto_update:
            self.UpdateWireOuts()
        return self.wire_ops.get_wire_out(ep_addr)

    def WriteToPipeIn(
        self,
        ep_addr: int,
        data: Union[str, bytearray, np.ndarray],
        reorder_str: bool = True,
    ) -> int:
        """
        Write data to a pipe-in endpoint.

        Transfers data from host to FPGA through the specified pipe endpoint.

        Args:
            ep_addr (int): Pipe endpoint address
            data (Union[str, bytearray]): Data to write
            reorder_str (bool): If True, reorder string data for FPGA (default: True)

        Returns:
            int: Number of bytes written

        Raises:
            ValueError: If data format is invalid
        """
        return self.pipe_ops.write_to_pipe_in(ep_addr, data, reorder_str)

    def ReadFromPipeOut(
        self, ep_addr: int, data: Union[int, bytearray], reorder_str: bool = True
    ) -> PipeOutData:
        """
        Read data from a pipe-out endpoint.

        Transfers data from FPGA to host through the specified pipe endpoint.

        Args:
            ep_addr (int): Pipe endpoint address
            data (Union[str, bytearray]): Buffer to store read data
            reorder_str (bool): If True, reorder received string data (default: True)

        Returns:
            PipeOutData: Object containing read data and error code

        Raises:
            ValueError: If data buffer format is invalid
        """
        return self.pipe_ops.read_from_pipe_out(ep_addr, data, reorder_str)

    def WriteToBlockPipeIn(
        self,
        ep_addr: int,
        data: Union[str, bytearray, np.ndarray],
        block_size: int = None,
        reorder_str: bool = True,
    ) -> int:
        """
        Write data to a block pipe-in endpoint.

        Transfers a block of data from host to FPGA through the specified block pipe endpoint.
        Block pipes are optimized for larger data transfers.

        Args:
            ep_addr (int): Block pipe endpoint address
            data (Union[str, bytearray]): Data block to write
            block_size (int): Number of bytes to write to the pipe
            reorder_str (bool): If True, reorder string data for FPGA (default: True)

        Returns:
            int: Number of bytes written

        Raises:
            ValueError: If data format is invalid
        """
        return self.block_pipe_ops.write_to_block_pipe_in(
            ep_addr, data, block_size, reorder_str=reorder_str
        )

    def ReadFromBlockPipeOut(
        self,
        ep_addr: int,
        data: Union[int, bytearray],
        block_size: int = None,
        reorder_str: bool = True,
    ) -> PipeOutData:
        """
        Read data from a block pipe-out endpoint.

        Transfers a block of data from FPGA to host through the specified block pipe endpoint.
        Block pipes are optimized for larger data transfers.

        Args:
            ep_addr (int): Block pipe endpoint address
            data (Union[int, bytearray]): Buffer to store read data
            block_size (int): Number of bytes to read from the pipe
            reorder_str (bool): If True, reorder received string data (default: True)

        Returns:
            PipeOutData: Object containing read data and error code

        Raises:
            ValueError: If data buffer format is invalid
        """
        return self.block_pipe_ops.read_from_block_pipe_out(
            ep_addr, data, block_size, reorder_str
        )

    def ActivateTriggerIn(self, ep_addr: int, bit: int) -> int:
        """
        Activate a trigger-in endpoint.

        Sends a trigger signal to the specified endpoint and bit.

        Args:
            ep_addr (int): Trigger endpoint address
            bit (int): Bit position to trigger (0-31)

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If bit position is invalid
        """
        return self.trigger_ops.activate_trigger_in(ep_addr, bit)

    def UpdateTriggerOuts(self) -> int:
        """
        Update all trigger-out endpoints.

        Reads the current state of all trigger-out endpoints from the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        return self.trigger_ops.update_trigger_outs()

    def IsTriggered(self, ep_addr: int, mask: int, auto_update: bool = False) -> bool:
        """
        Check if specific trigger bits are set.

        Args:
            ep_addr (int): Trigger endpoint address
            mask (int): Bit mask specifying which trigger bits to check
            auto_update (bool): If True, automatically update trigger states before checking (default: False)

        Returns:
            bool: True if any of the specified trigger bits are set

        Note:
            UpdateTriggerOuts() must be called before this method to get current trigger states.
        """
        if self.auto_trigger_out or auto_update:
            self.UpdateTriggerOuts()
        return self.trigger_ops.is_triggered(ep_addr, mask)

    def CheckTriggered(self, ep_addr: int, mask: int, timeout: float = 1.0):
        """
        Check if a trigger condition is met within a specified timeout.

        Args:
            ep_addr (int): Trigger endpoint address
            mask (int): Bit mask specifying which trigger bits to check
            timeout (float): Maximum time to wait for trigger condition, in seconds (default: 1)

        Raises:
            TimeoutError: If trigger condition is not met within the specified timeout
        """
        start_time = time.perf_counter()
        while True:
            if self.IsTriggered(ep_addr, mask, auto_update=True):
                return
            if time.perf_counter() - start_time > timeout:
                logger.error(
                    f"Trigger ({hex(ep_addr)}) condition not met within {timeout}s",
                )
                raise TimeoutError(
                    f"Trigger ({hex(ep_addr)}) condition not met within timeout"
                )

    def WriteRegister(self, addr: int, data: int) -> int:
        """
        Write a value to a register bridge.

        Args:
            addr (int): Register address (32-bit)
            data (int): Value to write (32-bit)

        Returns:
            int: Error code (0 on success)
        """
        validate_address(0, 2**32, addr)
        validate_wire_value(data, 32)

        return self.xem.WriteRegister(addr, data)

    def ReadRegister(self, addr: int) -> int:
        """
        Read a value from a register bridge.

        Args:
            addr (int): Register address (32-bit)

        Returns:
            int: Value read from the register
        """
        validate_address(0, 2**32, addr)

        return self.xem.ReadRegister(addr)


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
            TypeError: If connected device is not a XEM7310A75/A100
            Plus all exceptions from parent class __init__
        """
        super().__init__(bitstream_path=bitstream_path)

        target_product_id_list = [
            ok.okCFrontPanel.brdXEM7310A75,
            ok.okCFrontPanel.brdXEM7310A200,
        ]

        if self.config.product_id not in target_product_id_list:
            logger.critical("Connected FPGA board is not a XEM7310A75/A100!")
            raise TypeError("Connected FPGA board is not a XEM7310A75/A100!")

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

        target_product_id = ok.okCFrontPanel.brdXEM7360K160T

        if self.config.product_id != target_product_id:
            logger.critical("Connected FPGA board is not a XEM7360K160T!")
            raise TypeError("Connected FPGA board is not a XEM7360K160T!")

    def _check_device_settings(self) -> None:
        """
        Check voltage settings for XEM7360.

        Verifies I/O voltage settings for different banks and logs warnings
        if voltages are set below 120mV.
        """
        device_settings = ok.okCDeviceSettings()

        ok.okCFrontPanel.GetDeviceSettings(self.xem, device_settings)

        try:
            vadj_voltage_dict = {
                f"vadj{i}": device_settings.GetInt(f"XEM7360_VADJ{i}_VOLTAGE")
                for i in range(1, 3 + 1)
            }

            logger.info("Please check the I/O voltage settings.")
            logger.info(f"Bank 12 Voltage: {vadj_voltage_dict['vadj2']} mV")
            logger.info(f"Bank 15 Voltage: {vadj_voltage_dict['vadj1']} mV")
            logger.info(f"Bank 16 Voltage: {vadj_voltage_dict['vadj1']} mV")
            logger.info(f"Bank 32 Voltage: {vadj_voltage_dict['vadj3']} mV")

            vadj_modes = device_settings.GetInt("XEM7360_VADJ_MODE")

            vadj_mask = 0b0000_0011
            for i in range(1, 3 + 1):
                vadj_mode = vadj_modes & vadj_mask
                if vadj_mode < 2:
                    logger.warning(f"vadj{i} will be set to 120 mV!")
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
