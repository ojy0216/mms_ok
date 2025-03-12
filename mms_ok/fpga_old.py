import datetime
import logging
import os
import time
import types
from abc import ABC, abstractmethod
from typing import Optional, Type, Union

import numpy as np
import ok

from .utils import PipeOutData, log


class XEM(ABC):
    def __init__(self, bitstream_path: str) -> None:
        """
        Initializes the FPGA object.

        Args:
            bitstream_path (str): The path to the bitstream file.

        Returns:
            None
        """
        self._led_used = False
        self._led_address = None

        self.xem = ok.okCFrontPanel()

        self._bitstream_path = os.path.abspath(bitstream_path)

        self._validate_bitstream_path()

        self._connect()
        self._configure()
        self._check_device_settings()

        log("FPGA initialized!\n", logging_level=logging.INFO)

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
            log(f'"{self._bitstream_path}" is invalid!', logging_level=logging.CRITICAL)
            raise FileNotFoundError(f"{self._bitstream_path} is an invalid bitstream!")

        extension = os.path.splitext(self._bitstream_path)[1]
        if extension != ".bit":
            log(
                f"{extension} is not a valid bitstream file extension!",
                logging_level=logging.CRITICAL,
            )
            raise ValueError(f"{extension} is not a valid bitstream file extension!")

        log(f"Bitstream file: {self._bitstream_path}", logging_level=logging.INFO)

        timestamp = os.path.getmtime(self._bitstream_path)
        log(
            f"Bitstream date: {datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}",
            logging_level=logging.INFO,
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
        not_opened = self.xem.OpenBySerial("")
        if not_opened:
            log("Device is not opened!", logging_level=logging.CRITICAL)
            raise ConnectionError("Device is not opened!")
        else:
            log("Device is opened!", logging_level=logging.INFO)

        device_info = ok.okTDeviceInfo()
        self.xem.GetDeviceInfo(device_info)

        self._product_id = device_info.productID

        interface_list = ["Unknown", "USB 2", "PCIe", "USB 3"]

        # fmt: off
        log(f"Model         : {device_info.productName}", logging_level=logging.INFO)
        log(f"Serial        : {device_info.serialNumber}", logging_level=logging.INFO)
        log(f"Interface     : {interface_list[device_info.deviceInterface]}", logging_level=logging.INFO)
        log(f"Wire Width    : {device_info.wireWidth}", logging_level=logging.INFO)
        log(f"Trigger Width : {device_info.triggerWidth}", logging_level=logging.INFO)
        log(f"Pipe Width    : {device_info.pipeWidth}", logging_level=logging.INFO)
        # fmt: on

        self.wire_width = device_info.wireWidth
        self.trigger_width = device_info.triggerWidth

        if device_info.deviceInterface != ok.OK_INTERFACE_USB3:
            log("Device interface is not USB 3!", logging_level=logging.WARNING)
        if device_info.wireWidth != 32:
            log("Wire width is not 32!", logging_level=logging.WARNING)
        if device_info.triggerWidth != 32:
            log("Trigger width is not 32!", logging_level=logging.WARNING)
        if device_info.pipeWidth != 32:
            log("Pipe width is not 32!", logging_level=logging.WARNING)

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
        if error_code == 0:
            log(
                f"Input bitstream file is connected to the device!",
                logging_level=logging.INFO,
            )
        else:
            log(
                f"Input bitstream file is not connected to the device!",
                logging_level=logging.CRITICAL,
            )
            raise RuntimeError(f"Input bitstream file is not connected to the device!")

        if self.xem.IsFrontPanelEnabled():
            log("FrontPanel is enabled!", logging_level=logging.INFO)
        else:
            log("FrontPanel is not enabled!", logging_level=logging.CRITICAL)
            raise RuntimeError("FrontPanel is not enabled!")

    @abstractmethod
    def _check_device_settings(self) -> None:
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
        log("Closing device", logging_level=logging.INFO)
        if self._led_used:
            log(
                "Turning off the LEDs before closing the device!",
                logging_level=logging.INFO,
            )
            self.set_led(led_value=0, led_address=self._led_address)
        self.xem.Close()
        log("Device closed!", logging_level=logging.INFO)

    def reset(
        self, reset_address: int = 0x00, reset_time: float = 1, active_low=True
    ) -> None:
        """
        Resets the FPGA by toggling the specified reset address.

        Args:
            reset_address (int): The address of the reset wire. Should be in the range 0x00 ~ 0x1F. Defaults to 0x00.
            reset_time (float): The duration of the reset in seconds. Defaults to 1 second.
            active_low (bool): Determines whether the reset is active low or active high. Defaults to True (active low).

        Returns:
            None

        Raises:
            ValueError: If the reset_address is not in the range 0x00 ~ 0x1F.
        """
        if not 0x00 <= reset_address <= 0x1F:
            log(
                "Invalid reset_address! It should be in 0x00 ~ 0x1F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid reset_address! It should be in 0x00 ~ 0x1F")

        reset_value, nominal_value = (0, 1) if active_low else (1, 0)

        log(f"Reset Start ({reset_time}s)", logging_level=logging.INFO)
        self.SetWireInValue(reset_address, reset_value)
        self.UpdateWireIns()

        time.sleep(reset_time)

        self.SetWireInValue(reset_address, nominal_value)
        self.UpdateWireIns()
        log(f"Reset End ({reset_time}s)\n", logging_level=logging.INFO)

    @abstractmethod
    def set_led(self, num_leds: int, led_value: int, led_address: int = 0x00) -> None:
        if not 0 <= led_value < 2**num_leds:
            log(
                f"LED value must be between 0 and {2**num_leds - 1}",
                logging_level=logging.ERROR,
            )
            raise ValueError(f"LED value must be between 0 and {2**num_leds - 1}")

        self._led_used = True
        self._led_address = self._led_address or led_address
        log(
            f"Setting LED value to {led_value} ({np.binary_repr(led_value, width=num_leds)})",
            logging_level=logging.DEBUG,
        )

        self.SetWireInValue(self._led_address, led_value)
        self.UpdateWireIns()

    @staticmethod
    def reorder_hex_str(hex_str: str) -> str:
        """
        Reorders the hexadecimal string by swapping the positions of every 2 characters.

        Args:
            hex_str (str): The input hexadecimal string.

        Returns:
            str: The reordered hexadecimal string.

        Raises:
            ValueError: If the length of the input string is not a multiple of 8.

        Examples:
            Input: "AB_CD_EF_GH"
            Output: "GH_EF_CD_AB"
        """
        if len(hex_str) % 8 != 0:
            log(
                f"Hexadecimal string length must be a multiple of 8!",
                logging_level=logging.ERROR,
            )
            raise ValueError("Hexadecimal string length must be a multiple of 8!")

        return "".join(
            [
                hex_str[i + 6 : i + 8]
                + hex_str[i + 4 : i + 6]
                + hex_str[i + 2 : i + 4]
                + hex_str[i : i + 2]
                for i in range(0, len(hex_str), 8)
            ]
        )

    def SetWireInValue(
        self, epAddr: int, value: int, mask: Optional[int] = None
    ) -> int:
        """
        Sets the value of a wire in the FPGA.

        Args:
            epAddr (int): The endpoint address of the wire. Should be in the range 0x00 ~ 0x1F.
            value (int): The value to be set on the wire. Should be in the range 0 to (2**wire_width - 1).
            mask (int, optional): The mask to apply on the wire. Should be in the range 0 to (2**wire_width - 1).
                If not provided, the default mask is all 1's.

        Returns:
            int: The error code. Returns a negative value if the operation fails.

        Raises:
            ValueError: If the endpoint address is invalid or the value/mask is out of range.
        """
        if not 0x00 <= epAddr <= 0x1F:
            log(
                "Invalid endpoint address! It should be in 0x00 ~ 0x1F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0x00 ~ 0x1F")
        if not 0 <= value < (2**self.wire_width):
            log(
                f"Value ({value}) can't be represented with wire width ({self.wire_width})!",
                logging_level=logging.ERROR,
            )
            raise ValueError(
                f"Value ({value}) can't be represented with wire width ({self.wire_width})!"
            )
        if mask is None:
            # Default mask is all 1's
            mask = 2**self.wire_width - 1
        else:
            if not 0 <= mask < (2**self.wire_width):
                hex_str_len = int(2 * (np.log2(self.wire_width) - 1))
                log(
                    f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{(2**self.wire_width - 1):0{hex_str_len}_X}",
                    logging_level=logging.ERROR,
                )
                raise ValueError(
                    f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{(2**self.wire_width - 1):0{hex_str_len}_X}"
                )
        error_code = self.xem.SetWireInValue(epAddr, value, mask)
        if error_code < 0:
            log(
                f"SetWireInValue failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def UpdateWireIns(self) -> int:
        """
        Updates the wire-ins of the FPGA.

        Args:
            None

        Returns:
            int: The error code. Returns a negative value if an error occurs.
        """
        error_code = self.xem.UpdateWireIns()
        if error_code < 0:
            log(
                f"UpdateWireIns failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def UpdateWireOuts(self) -> int:
        """
        Updates the wire outs of the FPGA.

        Args:
            None

        Returns:
            int: The error code. Returns a negative value if an error occurs.
        """
        error_code = self.xem.UpdateWireOuts()
        if error_code < 0:
            log(
                f"UpdateWireOuts failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def GetWireOutValue(self, epAddr: int) -> int:
        """
        Retrieves the value of the specified wire out endpoint.

        Args:
            epAddr (int): The address of the wire out endpoint. Should be in the range 0x20 ~ 0x3F.

        Returns:
            int: The value of the wire out endpoint.

        Raises:
            ValueError: If the endpoint address is invalid.
        """
        if not 0x20 <= epAddr <= 0x3F:
            log(
                "Invalid endpoint address! It should be in 0x20 ~ 0x3F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0x20 ~ 0x3F")
        return self.xem.GetWireOutValue(epAddr)

    def WriteToPipeIn(
        self,
        epAddr: int,
        data: Union[str, bytearray],
        reorder_str: Optional[bool] = True,
    ) -> int:
        """
        Writes data to the specified endpoint address.

        Args:
            epAddr (int): The endpoint address to write to. Should be in the range 0x80 ~ 0x9F.
            data (Union[str, bytearray]): The data to write. Can be either a hexadecimal string or a bytearray.
            reorder_str (Optional[bool]): Whether to reorder the hexadecimal string before converting it to a bytearray.
                Defaults to True.

        Returns:
            int: The error code. Returns a negative value if the write operation fails.

        Raises:
            ValueError: If the endpoint address is invalid or the block size is not a multiple of 16 bytes.
        """
        if not 0x80 <= epAddr <= 0x9F:
            log(
                "Invalid endpoint address! It should be in 0x80 ~ 0x9F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0x80 ~ 0x9F")

        if isinstance(data, str):
            if reorder_str:
                data = bytearray.fromhex(self.reorder_hex_str(data))
            else:
                data = bytearray.fromhex(data)

        if len(data) % 16 != 0:
            log(
                "Block size must be a multiple of 16 bytes", logging_level=logging.ERROR
            )
            raise ValueError("Block size must be a multiple of 16 bytes")

        error_code = self.xem.WriteToPipeIn(epAddr, data)
        if error_code < 0:
            log(
                f"WriteToPipeIn failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def ReadFromPipeOut(
        self,
        epAddr: int,
        data: Optional[bytearray] = None,
        blockSize: Optional[int] = None,
        reorder_str: Optional[bool] = True,
    ) -> PipeOutData:
        """
        Reads data from the pipe out endpoint.

        Args:
            epAddr (int): The endpoint address. Should be in the range 0xA0 ~ 0xBF.
            data (Optional[bytearray]): The data to be read. If not provided, a bytearray of size `blockSize` will be created.
            blockSize (Optional[int]): The size of the data block to be read. If `data` is provided, this argument is ignored.
            reorder_str (Optional[bool]): Whether to reorder the hex string representation of the read data. Default is True.

        Returns:
            PipeOutData: An object containing the error code and the read data.

        Raises:
            ValueError: If the endpoint address is invalid or the block size is not a multiple of 16 bytes.
            RuntimeError: If both `data` and `blockSize` are None.
            TypeError: If `data` is provided but it is not a bytearray.
        """
        if not 0xA0 <= epAddr <= 0xBF:
            log(
                "Invalid endpoint address! It should be in 0xA0 ~ 0xBF",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0xA0 ~ 0xBF")

        if data is None and blockSize is None:
            log(
                "Both data and block size cannot be None at the same time",
                logging_level=logging.ERROR,
            )
            raise RuntimeError(
                "Both data and block size cannot be None at the same time"
            )
        elif blockSize is not None:
            # Only block size is provided
            data = bytearray(blockSize)
        elif data is not None:
            # Only data is provided
            if not isinstance(data, bytearray):
                log('Input "data" must be a bytearray!', logging_level=logging.ERROR)
                raise TypeError('Input "data" must be a bytearray!')
        else:
            # Both data and block size are provided
            if blockSize != len(data):
                log(
                    "Block size is not equal to the length of data",
                    logging_level=logging.WARNING,
                )

        if len(data) % 16 != 0:
            log(
                "Block size must be a multiple of 16 bytes", logging_level=logging.ERROR
            )
            raise ValueError("Block size must be a multiple of 16 bytes")

        error_code = self.xem.ReadFromPipeOut(epAddr, data)
        if error_code < 0:
            log(
                f"ReadFromPipeOut failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )

        if reorder_str:
            read_data = PipeOutData(
                error_code=error_code, data=self.reorder_hex_str(data.hex().upper())
            )
        else:
            read_data = PipeOutData(error_code=error_code, data=data.hex().upper())
        return read_data

    def WriteToBlockPipeIn(
        self,
        epAddr: int,
        data: Union[str, bytearray],
        blockSize: Optional[int] = None,
        reorder_str: Optional[bool] = True,
    ) -> int:
        """
        Writes data to the block pipe in the FPGA.

        Args:
            epAddr (int): The endpoint address to write to. It should be in the range 0x80 ~ 0x9F.
            data (Union[str, bytearray]): The data to be written. It can be either a hexadecimal string or a bytearray.
            blockSize (Optional[int]): The size of the data block. If not provided, it will be set to the length of the data.
            reorder_str (Optional[bool]): Specifies whether to reorder the hexadecimal string before converting it to a bytearray. Default is True.

        Returns:
            int: The error code. Returns a negative value if an error occurs.

        Raises:
            ValueError: If the endpoint address is invalid (not in the range 0x80 ~ 0x9F).
            ValueError: If the block size is not a multiple of 16 bytes.
        """
        if not 0x80 <= epAddr <= 0x9F:
            log(
                "Invalid endpoint address! It should be in 0x80 ~ 0x9F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0x80 ~ 0x9F")

        if isinstance(data, str):
            if reorder_str:
                data = bytearray.fromhex(self.reorder_hex_str(data))
            else:
                data = bytearray.fromhex(data)

        if blockSize is None:
            blockSize = len(data)

        if blockSize is not None and blockSize != len(data):
            log(
                "Block size is not equal to the length of data",
                logging_level=logging.WARNING,
            )

        if blockSize % 16 != 0:
            log(
                "Block size must be a multiple of 16 bytes", logging_level=logging.ERROR
            )
            raise ValueError("Block size must be a multiple of 16 bytes")

        error_code = self.xem.WriteToBlockPipeIn(epAddr, blockSize, data)
        if error_code < 0:
            log(
                f"WriteToBlockPipeIn failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def ReadFromBlockPipeOut(
        self,
        epAddr: int,
        data: Optional[bytearray] = None,
        blockSize: Optional[int] = None,
        reorder_str: Optional[bool] = True,
    ) -> PipeOutData:
        """
        Reads data from the block pipe out endpoint.

        Args:
            epAddr (int): The endpoint address. Should be in the range 0xA0 ~ 0xBF.
            data (Optional[bytearray]): The data to be read. If not provided, a bytearray of size `blockSize` will be created.
            blockSize (Optional[int]): The size of the data block to be read. If `data` is provided, this argument is ignored.
            reorder_str (Optional[bool]): Whether to reorder the hex string representation of the read data. Default is True.

        Returns:
            PipeOutData: An object containing the error code and the read data.

        Raises:
            ValueError: If the endpoint address is invalid or the block size is not a multiple of 16 bytes.
            RuntimeError: If both `data` and `blockSize` are None.
            TypeError: If `data` is provided but it is not a bytearray.
        """
        if not 0xA0 <= epAddr <= 0xBF:
            log(
                "Invalid endpoint address! It should be in 0xA0 ~ 0xBF",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0xA0 ~ 0xBF")

        if data is None and blockSize is None:
            log(
                "Both data and block size cannot be None at the same time",
                logging_level=logging.ERROR,
            )
            raise RuntimeError(
                "Both data and block size cannot be None at the same time"
            )
        elif blockSize is not None:
            # Only block size is provided
            data = bytearray(blockSize)
        elif data is not None:
            # Only data is provided
            if not isinstance(data, bytearray):
                log('Input "data" must be a bytearray!', logging_level=logging.ERROR)
                raise TypeError('Input "data" must be a bytearray!')
            blockSize = len(data)
        else:
            # Both data and block size are provided
            if blockSize != len(data):
                log(
                    "Block size is not equal to the length of data",
                    logging_level=logging.WARNING,
                )

        if blockSize % 16 != 0:
            log(
                "Block size must be a multiple of 16 bytes", logging_level=logging.ERROR
            )
            raise ValueError("Block size must be a multiple of 16 bytes")

        error_code = self.xem.ReadFromBlockPipeOut(epAddr, blockSize, data)
        if error_code < 0:
            log(
                f"ReadFromBlockPipeOut failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )

        if reorder_str:
            read_data = PipeOutData(
                error_code=error_code, data=self.reorder_hex_str(data.hex().upper())
            )
        else:
            read_data = PipeOutData(error_code=error_code, data=data.hex().upper())
        return read_data

    def ActivateTriggerIn(self, epAddr: int, bit: int) -> int:
        """
        Activates a trigger input on the FPGA.

        Args:
            epAddr (int): The endpoint address of the trigger input. Should be in the range 0x40 ~ 0x5F.
            bit (int): The bit number of the trigger input. Should be in the range 0 ~ 31.

        Returns:
            int: The error code. Returns a negative value if an error occurs.

        Raises:
            ValueError: If the endpoint address or bit is invalid.
        """
        if not 0x40 <= epAddr <= 0x5F:
            log(
                "Invalid endpoint address! It should be in 0x40 ~ 0x5F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0x40 ~ 0x5F")
        if not 0 <= bit < self.trigger_width:
            log(
                f"Invalid bit! It should be in 0 ~ {self.trigger_width - 1}",
                logging_level=logging.ERROR,
            )
            raise ValueError(
                f"Invalid bit! It should be in 0 ~ {self.trigger_width - 1}"
            )
        error_code = self.xem.ActivateTriggerIn(epAddr, bit)
        if error_code < 0:
            log(
                f"ActivateTriggerIn failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def UpdateTriggerOuts(self) -> int:
        """
        Updates the trigger outputs of the FPGA.

        Returns:
            int: The error code. Returns a negative value if an error occurs.
        """
        error_code = self.xem.UpdateTriggerOuts()
        if error_code < 0:
            log(
                f"UpdateTriggerOuts failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
                logging_level=logging.ERROR,
            )
        return error_code

    def IsTriggered(self, epAddr: int, mask: int) -> bool:
        """
        Checks if the specified endpoint address is triggered with the given mask.

        Args:
            epAddr (int): The endpoint address to check. It should be in the range 0x60 ~ 0x7F.
            mask (int): The mask value to compare against. It should be in the range 0 ~ (2**trigger_width - 1).

        Returns:
            bool: True if the endpoint address is triggered with the given mask, False otherwise.

        Raises:
            ValueError: If the endpoint address or mask is invalid.
        """
        if not 0x60 <= epAddr <= 0x7F:
            log(
                "Invalid endpoint address! It should be in 0x60 ~ 0x7F",
                logging_level=logging.ERROR,
            )
            raise ValueError("Invalid endpoint address! It should be in 0x60 ~ 0x7F")
        if not 0 <= mask < (2**self.trigger_width):
            hex_str_len = int(2 * (np.log2(self.wire_width) - 1))
            log(
                f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{(2**self.trigger_width - 1):0{hex_str_len}_X}",
                logging_level=logging.ERROR,
            )
            raise ValueError(
                f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{(2**self.trigger_width - 1):0{hex_str_len}_X}"
            )
        return self.xem.IsTriggered(epAddr, mask)


class XEM7310(XEM):
    def __init__(self, bitstream_path: str) -> None:
        """
        Initializes the FPGA object.

        Args:
            bitstream_path (str): The path to the bitstream file.

        Returns:
            None

        Raises:
            TypeError: If the connected FPGA board is not a XEM7310A75/A100.
        """
        super().__init__(bitstream_path=bitstream_path)

        target_product_id_list = [
            ok.okCFrontPanel.brdXEM7310A75,
            ok.okCFrontPanel.brdXEM7310A200,
        ]

        if self._product_id not in target_product_id_list:
            log(
                "Connected FPGA board is not a XEM7310A75/A100!",
                logging_level=logging.CRITICAL,
            )
            raise TypeError("Connected FPGA board is not a XEM7310A75/A100!")

    def _check_device_settings(self) -> None:
        pass

    def set_led(self, led_value: int, led_address: int = 0x00) -> None:
        """
        Sets the value of an LED on the FPGA board.

        Args:
            led_value (int): The value to set for the LED. Must be between 0 and 255 (inclusive).
            led_address (int, optional): The address of the LED. Defaults to 0x00.

        Raises:
            ValueError: If the LED value is not between 0 and 255.
        """
        # XEM7310 has 8 LEDs
        super().set_led(num_leds=8, led_value=led_value, led_address=led_address)


class XEM7360(XEM):
    class FPGA:
        def __init__(self, bitstream_path: str) -> None:
            """
            Initializes the FPGA object.

            Args:
                bitstream_path (str): The path to the bitstream file.

            Returns:
                None

            Raises:
                TypeError: If the connected FPGA board is not a XEM7360K160T.
            """
            super().__init__(bitstream_path=bitstream_path)

            target_product_id = ok.okCFrontPanel.brdXEM7360K160T

            if self._product_id != target_product_id:
                log(
                    "Connected FPGA board is not a XEM7360K160T!",
                    logging_level=logging.CRITICAL,
                )
                raise TypeError("Connected FPGA board is not a XEM7360K160T!")

    def _check_device_settings(self) -> None:
        """
        Checks the device settings for I/O voltage and displays the voltage values and warnings if necessary.

        This method retrieves the device settings for I/O voltage from the XEM7360 device and logs the voltage values
        for different banks. It also checks the voltage modes and displays warnings if the voltage is set to a value
        lower than 120 mV.

        Args:
            None

        Returns:
            None
        """
        device_settings = ok.okCDeviceSettings()

        ok.okCFrontPanel.GetDeviceSettings(self.xem, device_settings)

        vadj_voltage_dict = {
            f"vadj{i}": device_settings.GetInt(f"XEM7360_VADJ{i}_VOLTAGE")
            for i in range(1, 3 + 1)
        }

        log("Please check the I/O voltage settings.", logging_level=logging.INFO)
        log(
            f"Bank 12 Voltage: {vadj_voltage_dict['vadj2']} mV",
            logging_level=logging.INFO,
        )
        log(
            f"Bank 15 Voltage: {vadj_voltage_dict['vadj1']} mV",
            logging_level=logging.INFO,
        )
        log(
            f"Bank 16 Voltage: {vadj_voltage_dict['vadj1']} mV",
            logging_level=logging.INFO,
        )
        log(
            f"Bank 32 Voltage: {vadj_voltage_dict['vadj3']} mV",
            logging_level=logging.INFO,
        )

        vadj_modes = device_settings.GetInt("XEM7360_VADJ_MODE")

        vadj_mask = 0b0000_0011
        for i in range(1, 3 + 1):
            vadj_mode = vadj_modes & vadj_mask
            if vadj_mode < 2:
                log(f"vadj{i} will be set to 120 mV!", logging_level=logging.WARNING)
                log(
                    f"Please refer to https://docs.opalkelly.com/xem7360/device-settings/",
                    logging_level=logging.WARNING,
                )

            vadj_mask <<= 2

    def set_led(self, led_value: int, led_address: int = 0x00) -> None:
        """
        Sets the value of an LED on the FPGA board.

        Args:
            led_value (int): The value to set the LED to. Must be between 0 and 15 (inclusive).
            led_address (int, optional): The address of the LED. Defaults to 0x00.

        Returns:
            None

        Raises:
            ValueError: If the LED value is not between 0 and 15.
        """
        # XEM7360 has 4 LEDs
        super().set_led(num_leds=4, led_value=led_value, led_address=led_address)
