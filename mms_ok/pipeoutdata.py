from typing import Any, Optional

import numpy as np

from .diagnostics import log_error, log_warning


REORDER_STR_WARNING = "`reorder_str` is deprecated; use `endian` instead."
_ENDIAN_OMITTED = object()


def reorder_hex_words(hex_str: str, word_byte_width: int = 4) -> str:
    word_hex_width = word_byte_width * 2
    if len(hex_str) % word_hex_width != 0:
        message = (
            f"Hexadecimal string length must be a multiple of {word_hex_width}!"
        )
        log_error(message)
        raise ValueError(message)

    return "".join(
        "".join(
            hex_str[i + j : i + j + 2]
            for j in range(word_hex_width - 2, -1, -2)
        )
        for i in range(0, len(hex_str), word_hex_width)
    )


def validate_endian(endian: str) -> str:
    if endian not in ("little", "big"):
        message = "endian must be 'little' or 'big'"
        log_error(message)
        raise ValueError(message)
    return endian


def bytes_to_hex_words(
    data: bytearray, word_byte_width: int = 4, endian: str = "little"
) -> str:
    validate_endian(endian)
    if len(data) % word_byte_width != 0:
        message = f"Data length must be a multiple of {word_byte_width} bytes!"
        log_error(message)
        raise ValueError(message)

    word_hex_width = word_byte_width * 2
    return "".join(
        "{:0{}X}".format(
            int.from_bytes(data[i : i + word_byte_width], byteorder=endian),
            word_hex_width,
        )
        for i in range(0, len(data), word_byte_width)
    )


def reverse_hex_32bit_words(hex_str: str) -> str:
    word_hex_width = 8
    if len(hex_str) % word_hex_width != 0:
        message = (
            f"Hexadecimal string length must be a multiple of {word_hex_width}!"
        )
        log_error(message)
        raise ValueError(message)

    words = [
        hex_str[i : i + word_hex_width]
        for i in range(0, len(hex_str), word_hex_width)
    ]
    return "".join(reversed(words))


class PipeOutData:
    """
    Represents data received from a pipe out interface.

    Attributes:
        error_code (int): The successful FrontPanel return code associated with the data.
        raw_data (bytearray): The raw binary data received.
        hex_data (str): Hexadecimal string representation of the data.

    Methods:
        __repr__(): Returns a string representation of the data.
        __eq__(other): Checks if the data is equal to the given object.
        __ne__(other): Checks if the data is not equal to the given object.
        __len__(): Returns the length of the data.
        to_ndarray(dtype): Converts the data to a numpy array with the specified dtype.
    """

    def __init__(
        self,
        error_code: int,
        raw_data: bytearray,
        reorder_str: Optional[bool] = None,
        word_byte_width: int = 4,
        endian: Any = _ENDIAN_OMITTED,
        reverse: bool = False,
    ) -> None:
        """
        Initialize a PipeOutData object.

        Args:
            error_code (int): The successful FrontPanel return code associated with the data.
            raw_data (bytearray): The raw binary data received.
            reorder_str (bool): Deprecated; use endian instead.
            word_byte_width (int): Number of bytes in each word used for hex formatting.
            endian (str): Byte order used for formatted hex word data.
            reverse (bool): If True, format hex_data from latest 32-bit word first.
        """
        if endian is _ENDIAN_OMITTED:
            endian = "little"
            if reorder_str is not None:
                log_warning(REORDER_STR_WARNING)
                endian = "little" if reorder_str else "big"
        elif reorder_str is not None:
            log_warning(REORDER_STR_WARNING)
        validate_endian(endian)
        self.__error_code = error_code
        self.__raw_data = raw_data
        hex_data = bytes_to_hex_words(raw_data, word_byte_width, endian)
        if reverse:
            hex_data = reverse_hex_32bit_words(hex_data)
        self.__hex_data = hex_data

    @property
    def error_code(self) -> int:
        return self.__error_code

    @property
    def raw_data(self) -> bytearray:
        return self.__raw_data

    @property
    def hex_data(self) -> str:
        return self.__hex_data

    @property
    def transfer_byte(self) -> int:
        return max(self.__error_code, 0)

    def __repr__(self) -> str:
        return "PipeOutData(transfer_byte={}, hex_data={!r})".format(
            self.transfer_byte, self.hex_data
        )

    def __eq__(self, other) -> bool:
        if isinstance(other, PipeOutData):
            return self.hex_data == other.hex_data
        return self.hex_data == other

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self.hex_data)

    def to_ndarray(self, dtype: np.dtype) -> np.ndarray:
        """
        Convert the data to a numpy array with the specified dtype.

        Args:
            dtype: The data type of the numpy array (e.g., np.uint16, np.uint32)

        Returns:
            np.ndarray: The data as a numpy array

        Raises:
            TypeError: If the data cannot be converted to the specified dtype
        """
        return np.frombuffer(self.raw_data, dtype=dtype)
