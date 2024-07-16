import logging
import struct

from .logger import log

try:
    import torch
except ImportError:
    log("PyTorch is not available!", logging_level=logging.WARNING)
    torch_available = False
else:
    torch_available = True

try:
    import numpy as np
except ImportError:
    log("Numpy is not available!", logging_level=logging.WARNING)
    numpy_available = False
else:
    numpy_available = True


def convert_tensor_to_str(tensor: torch.Tensor) -> str:
    """
    Converts a PyTorch tensor to a hexadecimal string representation.

    Args:
        tensor (torch.Tensor): The input tensor to be converted.

    Returns:
        str: The hexadecimal string representation of the tensor.

    Raises:
        Exception: If PyTorch is not available.
        NotImplementedError: If the tensor is complex or 64-bit floating point.
    """
    if not torch_available:
        log("PyTorch is not available!", logging_level=logging.ERROR)
        raise ModuleNotFoundError("Pytorch is not available!")

    if tensor.dim() > 1:
        tensor = tensor.view(-1)

    if torch.is_complex(tensor):
        raise NotImplementedError("Complex tensor is not supported")

    numel = tensor.numel()
    element_size = tensor.element_size()
    element_str_len = element_size << 1

    if element_size > 4:
        raise NotImplementedError("64-bit floating point is not supported")

    if torch.is_floating_point(tensor):
        if tensor.dtype == torch.float16:
            hex_str = "".join(
                format(np.float16(t.item()).view(np.uint16), "04x") for t in tensor
            ).upper()
        else:
            hex_str = "".join(
                format(np.float32(t.item()).view(np.uint32), "08x")[:element_str_len]
                for t in tensor
            ).upper()
        assert len(hex_str) == numel * element_str_len
    else:
        raise NotImplementedError("Integer is not supported")

    return hex_str


def convert_str_to_tensor(hex_str: str, dtype: torch.dtype) -> torch.Tensor:
    """
    Converts a hexadecimal string to a PyTorch tensor.

    Args:
        hex_str (str): The hexadecimal string to convert.
        dtype (torch.dtype): The data type of the tensor.

    Returns:
        torch.Tensor: The converted tensor.

    Raises:
        Exception: If PyTorch is not available.

        NotImplementedError: If the data type is complex or not supported.
    """
    if not torch_available:
        log("PyTorch is not available!", logging_level=logging.ERROR)
        raise ModuleNotFoundError("Pytorch is not available!")

    if dtype.is_complex:
        raise NotImplementedError("Complex tensor is not supported")

    if dtype.is_floating_point:
        element_size = torch.zeros(size=(1,), dtype=dtype).element_size()

        if element_size > 4:
            raise NotImplementedError("64-bit floating point is not supported")

        element_str_len = element_size << 1
        numel = len(hex_str) // element_str_len

        if len(hex_str) % element_str_len != 0:
            log("Invalid hexadecimal string length!", logging_level=logging.ERROR)
            raise ValueError("Invalid hexadecimal string length!")

        data = [
            hex_str[element_str_len * i : element_str_len * (i + 1)]
            for i in range(numel)
        ]
        if dtype == torch.float16:
            data = [f"{d:04}" for d in data]
            data = [int(d, 16) for d in data]
            data = [struct.unpack("e", struct.pack("H", d))[0] for d in data]
        else:
            data = [f"{d:08}" for d in data]
            data = [int(d, 16) for d in data]
            data = [struct.unpack("f", struct.pack("I", d))[0] for d in data]
        data = torch.tensor(data, dtype=dtype)
    else:
        raise NotImplementedError("Integer is not supported")

    return data


def convert_ndarray_to_str(array: np.ndarray) -> str:
    """
    Converts a numpy ndarray to a hexadecimal string representation.

    Args:
        array (np.ndarray): The input numpy ndarray.

    Returns:
        str: The hexadecimal string representation of the input ndarray.

    Raises:
        Exception: If numpy is not available.

        NotImplementedError: If the array is complex or if 64-bit floating point or integer is not supported.
    """
    if not numpy_available:
        log("Numpy is not available!", logging_level=logging.ERROR)
        raise ModuleNotFoundError("Numpy is not available!")

    if array.ndim > 1:
        array = array.flatten()

    if np.iscomplexobj(array):
        raise NotImplementedError("Complex array is not supported")

    numel = array.size
    element_size = array.itemsize
    element_str_len = element_size << 1

    if element_size > 4:
        raise NotImplementedError("64-bit floating point is not supported")

    if np.issubdtype(array.dtype, np.floating):
        if array.dtype == np.float16:
            hex_str = "".join(
                format(np.float16(item).view(np.uint16), "04X") for item in array
            ).upper()
        else:
            hex_str = "".join(
                format(np.float32(item).view(np.uint32), "08X") for item in array
            )
        assert len(hex_str) == numel * element_str_len
    else:
        raise NotImplementedError("Integer is not supported")

    return hex_str


def convert_str_to_ndarray(hex_str: str, dtype=np.dtype) -> np.ndarray:
    """
    Convert a hexadecimal string to a numpy ndarray.

    Args:
        hex_str (str): The hexadecimal string to convert.
        dtype (numpy.dtype): The data type of the resulting ndarray.

    Returns:
        numpy.ndarray: The converted ndarray.

    Raises:
        Exception: If numpy is not available.

        NotImplementedError: If the data type is complex or not supported.
    """
    if not numpy_available:
        log("Numpy is not available!", logging_level=logging.ERROR)
        raise ModuleNotFoundError("Numpy is not available!")

    if np.issubdtype(dtype, np.complexfloating):
        raise NotImplementedError("Complex array is not supported")

    if np.issubdtype(dtype, np.floating):
        element_size = np.zeros(shape=(1,), dtype=dtype).itemsize

        if element_size > 4:
            raise NotImplementedError("64-bit floating point is not supported")

        element_str_len = element_size << 1
        numel = len(hex_str) // element_str_len

        if len(hex_str) % element_str_len != 0:
            log("Invalid hexadecimal string length!", logging_level=logging.ERROR)
            raise ValueError("Invalid hexadecimal string length!")

        data = [
            hex_str[element_str_len * i : element_str_len * (i + 1)]
            for i in range(numel)
        ]
        if dtype == np.float16:
            data = [f"{d:04}" for d in data]
            data = [int(d, 16) for d in data]
            data = [struct.unpack("e", struct.pack("H", d))[0] for d in data]
        else:
            data = [f"{d:08}" for d in data]
            data = [int(d, 16) for d in data]
            data = [struct.unpack("f", struct.pack("I", d))[0] for d in data]
        data = np.array(data, dtype=dtype)
    else:
        raise NotImplementedError("Integer is not supported")

    return data
