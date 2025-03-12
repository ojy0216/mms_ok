import numpy as np
import torch

from mms_ok.utils.conversion import (
    convert_ndarray_to_str,
    convert_str_to_ndarray,
    convert_str_to_tensor,
    convert_tensor_to_str,
)


def test_convert_tensor_to_str_1():
    # Test case 1: Convert a tensor of integers (should raise NotImplementedError)
    tensor1 = torch.tensor([1, 2, 3, 4])
    try:
        convert_tensor_to_str(tensor1)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_tensor_to_str_2():
    # Test case 2: Convert a tensor with complex numbers (should raise NotImplementedError)
    tensor2 = torch.tensor([1 + 2j, 3 + 4j])
    try:
        convert_tensor_to_str(tensor2)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_tensor_to_str_3():
    # Test case 3: Convert a tensor with 64-bit floating-point numbers (should raise NotImplementedError)
    tensor3 = torch.tensor([0.1, 0.2, 0.3, 0.4], dtype=torch.float64)
    try:
        convert_tensor_to_str(tensor3)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_tensor_to_str_4():
    # Test case 4: Convert a tensor of FP32 numbers
    tensor4 = torch.tensor(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=torch.float32
    )
    expected_result4 = "000000003dcccccd3e4ccccd3e99999a3ecccccd3f000000bdcccccdbe4ccccdbe99999abecccccdbf000000".upper()
    assert convert_tensor_to_str(tensor4) == expected_result4


def test_convert_tensor_to_str_5():
    # Test case 5: Convert a tensor of FP16 numbers
    tensor5 = torch.tensor(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=torch.float16
    )
    expected_result5 = "00002e66326634cd36663800ae66b266b4cdb666b800".upper()
    assert convert_tensor_to_str(tensor5) == expected_result5


def test_convert_tensor_to_str_6():
    # Test case 6: Convert a tensor of BF16 numbers
    tensor6 = torch.tensor(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=torch.bfloat16
    )
    expected_result6 = "00003dcd3e4d3e9a3ecd3f00bdcdbe4dbe9abecdbf00".upper()
    assert convert_tensor_to_str(tensor6) == expected_result6


def test_convert_str_to_tensor_1():
    # Test case 1: Convert a hexadecimal string to a tensor of integers
    hex_str1 = "01020304"
    try:
        convert_str_to_tensor(hex_str1, torch.int32)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_str_to_tensor_2():
    # Test case 2: Convert a hexadecimal string to a tensor of FP32 numbers
    hex_str2 = "000000003dcccccd3e4ccccd3e99999a3ecccccdbdcccccdbe4ccccdbe99999abecccccd".upper()
    expected_result2 = torch.tensor(
        [0, 0.1, 0.2, 0.3, 0.4, -0.1, -0.2, -0.3, -0.4], dtype=torch.float32
    )
    assert convert_str_to_tensor(hex_str2, torch.float32).equal(expected_result2)


def test_convert_str_to_tensor_3():
    # Test case 3: Convert a hexadecimal string to a tensor of FP16 numbers
    hex_str3 = "00002e66326634cd3666ae66b266b4cdb666".upper()
    expected_result3 = torch.tensor(
        [0, 0.1, 0.2, 0.3, 0.4, -0.1, -0.2, -0.3, -0.4], dtype=torch.float16
    )
    assert convert_str_to_tensor(hex_str3, torch.float16).equal(expected_result3)


def test_convert_str_to_tensor_4():
    # Test case 4: Convert a hexadecimal string to a tensor of BF16 numbers
    hex_str4 = "00003dcd3e4d3e9a3ecdbdcdbe4dbe9abecd".upper()
    expected_result4 = torch.tensor(
        [0, 0.1, 0.2, 0.3, 0.4, -0.1, -0.2, -0.3, -0.4], dtype=torch.bfloat16
    )
    assert convert_str_to_tensor(hex_str4, torch.bfloat16).equal(expected_result4)


def test_convert_ndarray_to_str_1():
    # Test case 1: Convert a ndarray of integers (should raise NotImplementedError)
    array1 = np.array([1, 2, 3, 4])
    try:
        convert_ndarray_to_str(array1)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_ndarray_to_str_2():
    # Test case 2: Convert a ndarray with complex numbers (should raise NotImplementedError)
    array2 = np.array([1 + 2j, 3 + 4j])
    try:
        convert_ndarray_to_str(array2)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_ndarray_to_str_3():
    # Test case 3: Convert a ndarray with 64-bit floating-point numbers (should raise NotImplementedError)
    array3 = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    try:
        convert_ndarray_to_str(array3)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_ndarray_to_str_4():
    # Test case 4: Convert a ndarray of FP32 numbers
    array4 = np.array(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=np.float32
    )
    expected_result4 = "000000003dcccccd3e4ccccd3e99999a3ecccccd3f000000bdcccccdbe4ccccdbe99999abecccccdbf000000".upper()
    assert convert_ndarray_to_str(array4) == expected_result4


def test_convert_ndarray_to_str_5():
    # Test case 5: Convert a ndarray of FP16 numbers
    array5 = np.array(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=np.float16
    )
    expected_result5 = "00002e66326634cd36663800ae66b266b4cdb666b800".upper()
    assert convert_ndarray_to_str(array5) == expected_result5


def test_convert_str_to_ndarray_1():
    # Test case 1: Convert a hexadecimal string to a ndarray of integers (should raise NotImplementedError)
    hex_str1 = "01020304"
    try:
        convert_str_to_ndarray(hex_str1, np.int32)
        assert False, "Expected NotImplementedError to be raised"
    except NotImplementedError:
        pass


def test_convert_str_to_ndarray_2():
    # Test case 2: Convert a hexadecimal string to a ndarray of FP32 numbers
    hex_str2 = "000000003dcccccd3e4ccccd3e99999a3ecccccd3f000000bdcccccdbe4ccccdbe99999abecccccdbf000000".upper()
    expected_result2 = np.array(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=np.float32
    )
    assert np.array_equal(
        convert_str_to_ndarray(hex_str2, np.float32), expected_result2
    )


def test_convert_str_to_ndarray_3():
    # Test case 3: Convert a hexadecimal string to a ndarray of FP16 numbers
    hex_str3 = "00002e66326634cd36663800ae66b266b4cdb666b800".upper()
    expected_result3 = np.array(
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2, -0.3, -0.4, -0.5], dtype=np.float16
    )
    assert np.array_equal(
        convert_str_to_ndarray(hex_str3, np.float16), expected_result3
    )
