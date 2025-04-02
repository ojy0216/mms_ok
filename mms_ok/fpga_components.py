from typing import Optional, Union

import numpy as np
import ok
from loguru import logger

from .pipeoutdata import PipeOutData
from .validation import validate_address, validate_block_size, validate_wire_value


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
        validate_address(0x00, 0x1F, ep_addr)
        validate_wire_value(value, self.wire_width)

        if mask is None:
            # Default mask is all 1's
            mask = (1 << self.wire_width) - 1
        else:
            if not 0 <= mask < (1 << self.wire_width):
                hex_str_len = int(2 * (np.log2(self.wire_width) - 1))
                logger.error(
                    f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{((1 << self.wire_width) - 1):0{hex_str_len}_X}",
                )
                raise ValueError(
                    f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{((1 << self.wire_width) - 1):0{hex_str_len}_X}"
                )

        error_code = self.xem.SetWireInValue(ep_addr, value, mask)
        if error_code < 0:
            logger.error(
                f"SetWireInValue failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

    def update_wire_ins(self) -> int:
        """
        Update all wire-in endpoints.

        Transfers all wire-in values that have been set using set_wire_in()
        to the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.xem.UpdateWireIns()
        if error_code < 0:
            logger.error(
                f"UpdateWireIns failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

    def update_wire_outs(self) -> int:
        """
        Update all wire-out endpoints.

        Reads the current state of all wire-out endpoints from the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.xem.UpdateWireOuts()
        if error_code < 0:
            logger.error(
                f"UpdateWireOuts failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

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
        validate_address(0x20, 0x3F, ep_addr)
        return self.xem.GetWireOutValue(ep_addr)


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
        validate_address(0x40, 0x5F, ep_addr)

        if not 0 <= bit < self.trigger_width:
            logger.error(
                f"Invalid bit! It should be in 0 ~ {self.trigger_width - 1}",
            )
            raise ValueError(
                f"Invalid bit! It should be in 0 ~ {self.trigger_width - 1}"
            )

        error_code = self.xem.ActivateTriggerIn(ep_addr, bit)
        if error_code < 0:
            logger.error(
                f"ActivateTriggerIn failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

    def update_trigger_outs(self) -> int:
        """
        Update all trigger-out endpoints.

        Reads the current state of all trigger-out endpoints from the FPGA device.

        Returns:
            int: Error code (0 on success)
        """
        error_code = self.xem.UpdateTriggerOuts()
        if error_code < 0:
            logger.error(
                f"UpdateTriggerOuts failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

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
        validate_address(0x60, 0x7F, ep_addr)

        if not 0 <= mask < (1 << self.trigger_width):
            hex_str_len = int(2 * (np.log2(self.trigger_width) - 1))
            logger.error(
                f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{((1 << self.trigger_width) - 1):0{hex_str_len}_X}",
            )
            raise ValueError(
                f"Invalid mask (0x{mask:0_X})! It should be in 0x{0:0{hex_str_len}_X} ~ 0x{((1 << self.trigger_width) - 1):0{hex_str_len}_X}"
            )

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
        if len(hex_str) % 8 != 0:
            logger.error(
                f"Hexadecimal string length must be a multiple of 8!",
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

    def _prepare_data(
        self, data: Union[str, bytearray, np.ndarray], reorder_str: bool
    ) -> bytearray:
        """
        Prepare data for pipe operations.

        Args:
            data: Data to prepare (string, bytearray, or numpy array)
            reorder_str: Whether to reorder string data

        Returns:
            bytearray: Prepared data

        Raises:
            ValueError: If data format is invalid
            TypeError: If data type is not supported
        """
        if isinstance(data, str):
            if reorder_str:
                data = bytearray.fromhex(self.reorder_hex_str(data))
            else:
                data = bytearray.fromhex(data)
        elif isinstance(data, np.ndarray):
            # data = data.tobytes()
            data = bytearray(data)
        elif not isinstance(data, bytearray):
            raise TypeError("Data must be a string, bytearray, or numpy array")

        if len(data) % 16 != 0:
            logger.error("Block size must be a multiple of 16 bytes")
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
                logger.error("Block size must be a multiple of 16 bytes")
                raise ValueError("Block size must be a multiple of 16 bytes")
            return bytearray(data)
        elif isinstance(data, bytearray):
            if len(data) % 16 != 0:
                logger.error("Block size must be a multiple of 16 bytes")
                raise ValueError("Block size must be a multiple of 16 bytes")
            return data
        else:
            raise TypeError("Data must be an integer or bytearray")

    def write_to_pipe_in(
        self,
        ep_addr: int,
        data: Union[str, bytearray, np.ndarray],
        reorder_str: bool = True,
    ) -> int:
        """
        Write data to a pipe-in endpoint.

        Args:
            ep_addr (int): Pipe endpoint address (0x80 - 0x9F)
            data: Data to write
            reorder_str (bool): Whether to reorder string data

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If endpoint address or data format is invalid
        """
        validate_address(0x80, 0x9F, ep_addr)

        prepared_data = self._prepare_data(data, reorder_str)

        error_code = self.xem.WriteToPipeIn(ep_addr, prepared_data)
        if error_code < 0:
            logger.error(
                f"WriteToPipeIn failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

    def read_from_pipe_out(
        self, ep_addr: int, data: Union[int, bytearray], reorder_str: bool = True
    ) -> PipeOutData:
        """
        Read data from a pipe-out endpoint.

        Args:
            ep_addr (int): Pipe endpoint address (0xA0 - 0xBF)
            data: Either a bytearray to use as buffer or an integer specifying buffer size
            reorder_str (bool): Whether to reorder received string data

        Returns:
            PipeOutData: Object containing read data and error code

        Raises:
            ValueError: If endpoint address or buffer format is invalid
        """
        validate_address(0xA0, 0xBF, ep_addr)

        buffer = self._prepare_read_buffer(data)

        error_code = self.xem.ReadFromPipeOut(ep_addr, buffer)
        if error_code < 0:
            logger.error(
                f"ReadFromPipeOut failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )

        # Create PipeOutData with raw buffer and reorder flag
        read_data = PipeOutData(
            error_code=error_code, raw_data=buffer, reorder_str=reorder_str
        )
        return read_data


class BlockPipeOperations:
    """
    Interface for block pipe data transfer operations on FPGA devices.

    Provides methods for transferring blocks of data between host and FPGA using block pipes.
    Block pipes are optimized for larger data transfers.

    Attributes:
        xem (ok.okCFrontPanel): Low-level interface to the FPGA device
    """

    def __init__(self, xem: ok.okCFrontPanel, bt_max_blocksize: int):
        """
        Initialize block pipe operations interface.

        Args:
            xem (ok.okCFrontPanel): Low-level interface to the FPGA device
        """
        self.xem = xem
        self.pipe_ops = PipeOperations(xem)
        self.bt_max_blocksize = bt_max_blocksize

    def write_to_block_pipe_in(
        self,
        ep_addr: int,
        data: Union[str, bytearray, np.ndarray],
        block_size: int = None,
        reorder_str: bool = True,
    ) -> int:
        """
        Write data to a block pipe-in endpoint.

        Args:
            ep_addr (int): Block pipe endpoint address (0x80 - 0x9F)
            data: Data to write
            block_size (int): Number of bytes to write to the pipe
            reorder_str (bool): Whether to reorder string data

        Returns:
            int: Error code (0 on success)

        Raises:
            ValueError: If endpoint address or data format is invalid
        """
        validate_address(0x80, 0x9F, ep_addr)

        prepared_data = self.pipe_ops._prepare_data(data, reorder_str)

        if block_size is None:
            block_size = (
                min(len(prepared_data), self.bt_max_blocksize)
                if self.bt_max_blocksize > 0
                else len(prepared_data)
            )
        else:
            validate_block_size(block_size, self.bt_max_blocksize)

        error_code = self.xem.WriteToBlockPipeIn(ep_addr, block_size, prepared_data)
        if error_code < 0:
            logger.error(
                f"WriteToBlockPipeIn failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )
        return error_code

    def read_from_block_pipe_out(
        self,
        ep_addr: int,
        data: Union[int, bytearray],
        block_size: int = None,
        reorder_str: bool = True,
    ) -> PipeOutData:
        """
        Read data from a block pipe-out endpoint.

        Args:
            ep_addr (int): Block pipe endpoint address (0xA0 - 0xBF)
            data: Either a bytearray to use as buffer or an integer specifying buffer size
            block_size (int): Number of bytes to read from the pipe
            reorder_str (bool): Whether to reorder received string data

        Returns:
            PipeOutData: Object containing read data and error code

        Raises:
            ValueError: If endpoint address or buffer format is invalid
        """
        validate_address(0xA0, 0xBF, ep_addr)

        buffer = self.pipe_ops._prepare_read_buffer(data)

        if block_size is None:
            block_size = (
                min(len(buffer), self.bt_max_blocksize)
                if self.bt_max_blocksize > 0
                else len(buffer)
            )
        else:
            validate_block_size(block_size, self.bt_max_blocksize)

        error_code = self.xem.ReadFromBlockPipeOut(ep_addr, block_size, buffer)
        if error_code < 0:
            logger.error(
                f"ReadFromBlockPipeOut failed - {ok.okCFrontPanel.GetErrorString(error_code)}",
            )

        # Create PipeOutData with raw buffer and reorder flag
        read_data = PipeOutData(
            error_code=error_code, raw_data=buffer, reorder_str=reorder_str
        )
        return read_data
