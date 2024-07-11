class PipeOutData:
    """
    Represents data received from a pipe out interface.

    Attributes:
        error_code (int): The error code associated with the data.
        data (str): The actual data received.

    Methods:
        __repr__(): Returns a string representation of the data.
        __eq__(other): Checks if the data is equal to the given object.
        __ne__(other): Checks if the data is not equal to the given object.
        __len__(): Returns the length of the data.
    """

    def __init__(self, error_code: int, data: str) -> None:
        self.__error_code = error_code
        self.__data = data

    @property
    def error_code(self) -> int:
        return self.__error_code

    @property
    def data(self) -> str:
        return self.__data

    def __repr__(self) -> str:
        return self.__data

    def __eq__(self, other) -> bool:
        return self.__data == other

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self.__data)
