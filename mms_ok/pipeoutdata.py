import numpy as np
from loguru import logger


class PipeOutData:
    """
    Represents data received from a pipe out interface.

    Attributes:
        error_code (int): The error code associated with the data.
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
        self, error_code: int, raw_data: bytearray, reorder_str: bool = False
    ) -> None:
        """
        Initialize a PipeOutData object.

        Args:
            error_code (int): The error code associated with the data.
            raw_data (bytearray): The raw binary data received.
            reorder_str (bool): Whether to reorder the hex string representation.
        """
        self.__error_code = error_code
        self.__raw_data = raw_data

        # Generate hex string representation
        hex_str = raw_data.hex().upper()

        # Reorder if requested
        if reorder_str:
            # Reorder the hexadecimal string by swapping the positions of every 2 characters
            if len(hex_str) % 8 != 0:
                logger.error("Hexadecimal string length must be a multiple of 8!")
                raise ValueError("Hexadecimal string length must be a multiple of 8!")

            self.__hex_data = "".join(
                [
                    hex_str[i + 6 : i + 8]
                    + hex_str[i + 4 : i + 6]
                    + hex_str[i + 2 : i + 4]
                    + hex_str[i : i + 2]
                    for i in range(0, len(hex_str), 8)
                ]
            )
        else:
            self.__hex_data = hex_str

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
        return self.hex_data

    def __eq__(self, other) -> bool:
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
