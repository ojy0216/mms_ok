from __future__ import annotations

from typing import Any, Optional, Union

import numpy as np

from .address import (
    BLOCK_PIPE_IN_END,
    BLOCK_PIPE_IN_START,
    BLOCK_PIPE_OUT_END,
    BLOCK_PIPE_OUT_START,
    PIPE_IN_END,
    PIPE_IN_START,
    PIPE_OUT_END,
    PIPE_OUT_START,
    TRIGGER_IN_END,
    TRIGGER_IN_START,
    TRIGGER_OUT_END,
    TRIGGER_OUT_START,
    WIRE_IN_END,
    WIRE_IN_START,
    WIRE_OUT_END,
    WIRE_OUT_START,
)
from .diagnostics import log_error, log_warning
from .ok_setup import get_ok
from .pipeoutdata import (
    REORDER_STR_WARNING,
    PipeOutData,
    reorder_hex_words,
    validate_endian,
)
from .validation import (
    BlockPipeTransportPolicy,
    validate_address,
    validate_wire_value,
)


_ENDIAN_OMITTED = object()


def _resolve_pipe_endian(endian: Any, reorder_str: Optional[bool]) -> str:
    if endian is _ENDIAN_OMITTED:
        if reorder_str is None:
            return "little"
        log_warning(REORDER_STR_WARNING)
        return "little" if reorder_str else "big"
    if isinstance(endian, bool):
        log_warning(REORDER_STR_WARNING)
        return "little" if endian else "big"
    if reorder_str is not None:
        log_warning(REORDER_STR_WARNING)
    validate_endian(endian)
    return endian


def _format_hex_for_bit_width(value: int, bit_width: int) -> str:
    hex_digits = max(1, (bit_width + 3) // 4)  # Calculate required hex digits
    separator_count = (hex_digits - 1) // 4
    display_width = hex_digits + separator_count
    return f"0x{value:0{display_width}_X}"


def _check_error_code(error_code: int, operation: str, failure_message: str) -> int:
    if error_code < 0:
        ok = get_ok()
        error_str = ok.okCFrontPanel.GetErrorString(error_code)
        log_error(f"{operation} failed - {error_str}")
        raise RuntimeError(f"{failure_message} ({error_str})")
    return error_code


class WireOperations:
    """
    Interface for wire-based I/O operations on FPGA devices.

    Provides methods for setting and getting wire values, and updating
    wire states between the host and FPGA.

    Attributes:
        xem (ok.okCFrontPanel): Low-level interface to the FPGA device
        wire_width (int): Bit width of wire endpoints (typically 32)
    """

    def __init__(self, xem: ok.okCFrontPanel, wire_width: int):
        """
        Initialize wire operations interface.

        Args:
            xem (ok.okCFrontPanel): Low-level interface to the FPGA device
            wire_width (int): Bit width of wire endpoints
        """
        self.xem = xem
        self.wire_width = wire_width

    def set_wire_in(self, ep_addr: int, value: int, mask: Optional[int] = None) -> int:
        """
        Set a value to be written to a wire-in endpoint.

        Args:
            ep_addr (int): Wire endpoint address (0x00 - 0x1F)
            value (int): Value to write
            mask (Optional[int]): Bit mask to apply to value

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If endpoint address or value is invalid
        """
        validate_address(WIRE_IN_START, WIRE_IN_END, ep_addr)
        validate_wire_value(value, self.wire_width)

        if mask is None:
            # Default mask is all 1's
            mask = (1 << self.wire_width) - 1
        else:
            if not 0 <= mask < (1 << self.wire_width):
                message = (
                    f"Invalid mask (0x{mask:0_X})! It should be in "
                    f"{_format_hex_for_bit_width(0, self.wire_width)} ~ "
                    f"{_format_hex_for_bit_width((1 << self.wire_width) - 1, self.wire_width)}"
                )
                log_error(message)
                raise ValueError(message)

        error_code = self.xem.SetWireInValue(ep_addr, value, mask)
        return _check_error_code(
            error_code, "SetWireInValue", "Failed to set wire-in value"
        )

    def update_wire_ins(self) -> int:
        """
        Update all wire-in endpoints.

        Transfers all wire-in values that have been set using set_wire_in()
        to the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.xem.UpdateWireIns()
        return _check_error_code(
            error_code, "UpdateWireIns", "Failed to update wire-ins"
        )

    def update_wire_outs(self) -> int:
        """
        Update all wire-out endpoints.

        Reads the current state of all wire-out endpoints from the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.xem.UpdateWireOuts()
        return _check_error_code(
            error_code, "UpdateWireOuts", "Failed to update wire-outs"
        )

    def get_wire_out(self, ep_addr: int) -> int:
        """
        Get the value of a wire-out endpoint.

        Args:
            ep_addr (int): Wire endpoint address (0x20 - 0x3F)

        Returns:
            int: Current value of the specified wire-out endpoint

        Raises:
            ValueError: If endpoint address is invalid

        Note:
            update_wire_outs() must be called before this method to get current values.
        """
        validate_address(WIRE_OUT_START, WIRE_OUT_END, ep_addr)
        return_data = self.xem.GetWireOutValue(ep_addr)
        error_code = self.xem.GetLastError()
        _check_error_code(error_code, "GetWireOutValue", "Failed to get wire-out value")
        return return_data


class TriggerOperations:
    """
    Interface for trigger-based operations on FPGA devices.

    Provides methods for activating triggers and checking trigger states.

    Attributes:
        xem (ok.okCFrontPanel): Low-level interface to the FPGA device
        trigger_width (int): Bit width of trigger endpoints (typically 32)
    """

    def __init__(self, xem: ok.okCFrontPanel, trigger_width: int):
        """
        Initialize trigger operations interface.

        Args:
            xem (ok.okCFrontPanel): Low-level interface to the FPGA device
            trigger_width (int): Bit width of trigger endpoints
        """
        self.xem = xem
        self.trigger_width = trigger_width

    def activate_trigger_in(self, ep_addr: int, bit: int) -> int:
        """
        Activate a trigger-in endpoint.

        Sends a trigger signal to the specified endpoint and bit.

        Args:
            ep_addr (int): Trigger endpoint address (0x40 - 0x5F)
            bit (int): Bit position to trigger (0-31)

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If endpoint address or bit position is invalid
        """
        validate_address(TRIGGER_IN_START, TRIGGER_IN_END, ep_addr)

        if not 0 <= bit < self.trigger_width:
            message = f"Invalid bit! It should be in 0 ~ {self.trigger_width - 1}"
            log_error(message)
            raise ValueError(message)

        error_code = self.xem.ActivateTriggerIn(ep_addr, bit)
        return _check_error_code(
            error_code, "ActivateTriggerIn", "Failed to activate trigger-in"
        )

    def update_trigger_outs(self) -> int:
        """
        Update all trigger-out endpoints.

        Reads the current state of all trigger-out endpoints from the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.xem.UpdateTriggerOuts()
        return _check_error_code(
            error_code, "UpdateTriggerOuts", "Failed to update trigger-outs"
        )

    def is_triggered(self, ep_addr: int, mask: int) -> bool:
        """
        Check if specific trigger bits are set.

        Args:
            ep_addr (int): Trigger endpoint address (0x60 - 0x7F)
            mask (int): Bit mask specifying which trigger bits to check

        Returns:
            bool: True if any of the specified trigger bits are set

        Raises:
            ValueError: If endpoint address or mask is invalid

        Note:
            update_trigger_outs() must be called before this method to get current trigger states.
        """
        validate_address(TRIGGER_OUT_START, TRIGGER_OUT_END, ep_addr)

        if not 0 <= mask < (1 << self.trigger_width):
            hex_str_len = int(2 * (np.log2(self.trigger_width) - 1))
            message = (
                f"Invalid mask (0x{mask:0_X})! It should be in "
                f"{_format_hex_for_bit_width(0, self.trigger_width)} ~ "
                f"{_format_hex_for_bit_width((1 << self.trigger_width) - 1, self.trigger_width)}"
            )
            log_error(message)
            raise ValueError(message)

        return self.xem.IsTriggered(ep_addr, mask)


class PipeOperations:
    """
    Interface for pipe data transfer operations on FPGA devices.

    Provides methods for transferring data between host and FPGA using pipes.

    Attributes:
        xem (ok.okCFrontPanel): Low-level interface to the FPGA device
    """

    def __init__(self, xem: ok.okCFrontPanel):
        """
        Initialize pipe operations interface.

        Args:
            xem (ok.okCFrontPanel): Low-level interface to the FPGA device
        """
        self.xem = xem

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
        return reorder_hex_words(hex_str)

    @staticmethod
    def _hex_words_to_bytearray(
        hex_str: str, word_byte_width: int, endian: str
    ) -> bytearray:
        word_hex_width = word_byte_width * 2
        normalized_hex = bytearray.fromhex(hex_str).hex()
        if len(normalized_hex) % word_hex_width != 0:
            message = (
                f"Hexadecimal string length must be a multiple of {word_hex_width}!"
            )
            log_error(message)
            raise ValueError(message)

        return bytearray(
            b"".join(
                int(normalized_hex[i : i + word_hex_width], 16).to_bytes(
                    word_byte_width, byteorder=endian
                )
                for i in range(0, len(normalized_hex), word_hex_width)
            )
        )

    @staticmethod
    def _ndarray_to_bytearray(data: np.ndarray, endian: str) -> bytearray:
        contiguous = np.ascontiguousarray(data)
        if np.issubdtype(contiguous.dtype, np.integer):
            target_dtype = contiguous.dtype.newbyteorder(
                "<" if endian == "little" else ">"
            )
            return bytearray(contiguous.astype(target_dtype, copy=False).tobytes())
        return bytearray(contiguous.tobytes())

    def _prepare_data(
        self,
        data: Union[str, bytearray, np.ndarray],
        endian: str = "little",
    ) -> bytearray:
        """
        Prepare data for pipe operations.

        Args:
            data: Data to prepare (string, bytearray, or numpy array)
            endian: Byte order used for string and integer numpy array data

        Returns:
            bytearray: Prepared data

        Raises:
            ValueError: If data format is invalid
            TypeError: If data type is not supported
        """
        validate_endian(endian)
        if isinstance(data, str):
            data = self._hex_words_to_bytearray(data, 4, endian)
        elif isinstance(data, np.ndarray):
            data = self._ndarray_to_bytearray(data, endian)
        elif not isinstance(data, bytearray):
            raise TypeError("Data must be a string, bytearray, or numpy array")

        if len(data) % 16 != 0:
            log_error("Block size must be a multiple of 16 bytes")
            raise ValueError("Block size must be a multiple of 16 bytes")

        return data

    def _prepare_read_buffer(self, data: Union[int, bytearray]) -> bytearray:
        """
        Prepare buffer for reading data.

        Args:
            data: Either a bytearray to use as buffer or an integer specifying buffer size

        Returns:
            bytearray: Prepared buffer

        Raises:
            ValueError: If buffer size is invalid
            TypeError: If data type is not supported
        """
        if isinstance(data, int):
            if data % 16 != 0:
                log_error("Block size must be a multiple of 16 bytes")
                raise ValueError("Block size must be a multiple of 16 bytes")
            return bytearray(data)
        elif isinstance(data, bytearray):
            if len(data) % 16 != 0:
                log_error("Block size must be a multiple of 16 bytes")
                raise ValueError("Block size must be a multiple of 16 bytes")
            return data
        else:
            raise TypeError("Data must be an integer or bytearray")

    def write_to_pipe_in(
        self,
        ep_addr: int,
        data: Union[str, bytearray, np.ndarray],
        endian: Union[str, bool] = _ENDIAN_OMITTED,
        reorder_str: Optional[bool] = None,
    ) -> int:
        """
        Write data to a pipe-in endpoint.

        Args:
            ep_addr (int): Pipe endpoint address (0x80 - 0x9F)
            data: Data to write
            endian (str): Byte order used for string and integer numpy array data
            reorder_str (bool): Deprecated; use endian instead

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If endpoint address or data format is invalid
        """
        endian = _resolve_pipe_endian(endian, reorder_str)
        validate_address(PIPE_IN_START, PIPE_IN_END, ep_addr)

        prepared_data = self._prepare_data(data, endian)

        error_code = self.xem.WriteToPipeIn(ep_addr, prepared_data)
        return _check_error_code(
            error_code, "WriteToPipeIn", "Failed to write to pipe-in"
        )

    def read_from_pipe_out(
        self,
        ep_addr: int,
        data: Union[int, bytearray],
        endian: Union[str, bool] = _ENDIAN_OMITTED,
        reorder_str: Optional[bool] = None,
    ) -> PipeOutData:
        """
        Read data from a pipe-out endpoint.

        Args:
            ep_addr (int): Pipe endpoint address (0xA0 - 0xBF)
            data: Either a bytearray to use as buffer or an integer specifying buffer size
            endian (str): Byte order used for formatted hex word data
            reorder_str (bool): Deprecated; use endian instead

        Returns:
            PipeOutData: Object containing read data and successful return code

        Raises:
            ValueError: If endpoint address or buffer format is invalid
            RuntimeError: If the FrontPanel read operation returns an error code
        """
        endian = _resolve_pipe_endian(endian, reorder_str)
        validate_address(PIPE_OUT_START, PIPE_OUT_END, ep_addr)

        buffer = self._prepare_read_buffer(data)

        error_code = self.xem.ReadFromPipeOut(ep_addr, buffer)
        _check_error_code(error_code, "ReadFromPipeOut", "Failed to read from pipe-out")

        return PipeOutData(
            error_code=error_code,
            raw_data=buffer,
            endian=endian,
        )


class BlockPipeOperations:
    """
    Interface for block pipe data transfer operations on FPGA devices.

    Provides methods for transferring blocks of data between host and FPGA using block pipes.
    Block pipes are optimized for larger data transfers.

    Attributes:
        xem (ok.okCFrontPanel): Low-level interface to the FPGA device
    """

    def __init__(
        self,
        xem: ok.okCFrontPanel,
        bt_max_blocksize: int,
        usb_speed: str = "SUPER",
        device_interface: str = "USB 3",
    ):
        """
        Initialize block pipe operations interface.

        Args:
            xem (ok.okCFrontPanel): Low-level interface to the FPGA device
        """
        self.xem = xem
        self.pipe_ops = PipeOperations(xem)
        self.bt_max_blocksize = bt_max_blocksize
        self.usb_speed = usb_speed
        self.device_interface = device_interface
        self._transport_policy = BlockPipeTransportPolicy(
            bt_max_blocksize,
            usb_speed=usb_speed,
            device_interface=device_interface,
        )

    def _word_byte_width(self) -> int:
        return self._transport_policy.word_byte_width

    def _prepare_data(
        self,
        data: Union[str, bytearray, np.ndarray],
        endian: str = "little",
    ) -> bytearray:
        validate_endian(endian)
        if isinstance(data, str):
            data = PipeOperations._hex_words_to_bytearray(
                data, self._word_byte_width(), endian
            )
        elif isinstance(data, np.ndarray):
            data = PipeOperations._ndarray_to_bytearray(data, endian)
        elif not isinstance(data, bytearray):
            raise TypeError("Data must be a string, bytearray, or numpy array")
        return data

    def _prepare_read_buffer(self, data: Union[int, bytearray]) -> bytearray:
        if isinstance(data, int):
            return bytearray(data)
        if isinstance(data, bytearray):
            return data
        raise TypeError("Data must be an integer or bytearray")

    def _select_block_size(self, transfer_byte: int) -> int:
        return self._transport_policy.select_block_size(transfer_byte)

    def write_to_block_pipe_in(
        self,
        ep_addr: int,
        data: Union[str, bytearray, np.ndarray],
        block_size: int = None,
        endian: Union[str, bool] = _ENDIAN_OMITTED,
        reorder_str: Optional[bool] = None,
    ) -> int:
        """
        Write data to a block pipe-in endpoint.

        Args:
            ep_addr (int): Block pipe endpoint address (0x80 - 0x9F)
            data: Data to write
            block_size (int): Number of bytes to write to the pipe
            endian (str): Byte order used for string and integer numpy array data
            reorder_str (bool): Deprecated; use endian instead

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If endpoint address or data format is invalid
        """
        endian = _resolve_pipe_endian(endian, reorder_str)
        validate_address(BLOCK_PIPE_IN_START, BLOCK_PIPE_IN_END, ep_addr)

        prepared_data = self._prepare_data(data, endian)

        if block_size is None:
            block_size = self._select_block_size(len(prepared_data))
        else:
            self._transport_policy.validate_block_size(block_size, len(prepared_data))

        error_code = self.xem.WriteToBlockPipeIn(ep_addr, block_size, prepared_data)
        return _check_error_code(
            error_code, "WriteToBlockPipeIn", "Failed to write to block pipe-in"
        )

    def read_from_block_pipe_out(
        self,
        ep_addr: int,
        data: Union[int, bytearray],
        block_size: int = None,
        endian: Union[str, bool] = _ENDIAN_OMITTED,
        reorder_str: Optional[bool] = None,
    ) -> PipeOutData:
        """
        Read data from a block pipe-out endpoint.

        Args:
            ep_addr (int): Block pipe endpoint address (0xA0 - 0xBF)
            data: Either a bytearray to use as buffer or an integer specifying buffer size
            block_size (int): Number of bytes to read from the pipe
            endian (str): Byte order used for formatted hex word data
            reorder_str (bool): Deprecated; use endian instead

        Returns:
            PipeOutData: Object containing read data and successful return code

        Raises:
            ValueError: If endpoint address or buffer format is invalid
            RuntimeError: If the FrontPanel read operation returns an error code
        """
        endian = _resolve_pipe_endian(endian, reorder_str)
        validate_address(BLOCK_PIPE_OUT_START, BLOCK_PIPE_OUT_END, ep_addr)

        buffer = self._prepare_read_buffer(data)

        if block_size is None:
            block_size = self._select_block_size(len(buffer))
        else:
            self._transport_policy.validate_block_size(block_size, len(buffer))

        error_code = self.xem.ReadFromBlockPipeOut(ep_addr, block_size, buffer)
        _check_error_code(
            error_code, "ReadFromBlockPipeOut", "Failed to read from block pipe-out"
        )

        return PipeOutData(
            error_code=error_code,
            raw_data=buffer,
            word_byte_width=self._word_byte_width(),
            endian=endian,
        )
