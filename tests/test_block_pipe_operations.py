from __future__ import annotations

import pytest

from mms_ok.fpga_config import FPGAConfig
from mms_ok import fpga_components
from mms_ok.fpga_components import BlockPipeOperations, PipeOperations
from mms_ok.validation import validate_block_size


class FakeOk:
    class okCFrontPanel:
        @staticmethod
        def GetErrorString(error_code):
            return "mock error {}".format(error_code)


class FakePipeXem:
    def __init__(self, read_error=16) -> None:
        self.read_error = read_error

    def ReadFromPipeOut(self, ep_addr, data):
        return self.read_error


class FakeBlockPipeXem:
    def __init__(self, read_error=None) -> None:
        self.block_pipe_in_calls = []
        self.block_pipe_out_calls = []
        self.read_error = read_error

    def WriteToBlockPipeIn(self, ep_addr, block_size, data):
        self.block_pipe_in_calls.append((ep_addr, block_size, len(data)))
        return len(data)

    def ReadFromBlockPipeOut(self, ep_addr, block_size, data):
        self.block_pipe_out_calls.append((ep_addr, block_size, len(data)))
        if self.read_error is not None:
            return self.read_error
        return len(data)


class FakeDeviceInfo:
    productName = "Fake"
    serialNumber = "1234"
    productID = 1
    wireWidth = 32
    triggerWidth = 32
    pipeWidth = 32

    def __init__(self, device_interface, usb_speed) -> None:
        self.deviceInterface = device_interface
        self.usbSpeed = usb_speed


def test_write_to_block_pipe_in_uses_largest_block_size_that_divides_transfer():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    ops.write_to_block_pipe_in(0x80, bytearray(16384 * 5))

    assert xem.block_pipe_in_calls == [(0x80, 16384, 16384 * 5)]


def test_write_to_block_pipe_in_falls_back_to_16_for_non_divisible_superspeed_size():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    ops.write_to_block_pipe_in(0x80, bytearray(16 * 1025))

    assert xem.block_pipe_in_calls == [(0x80, 16, 16 * 1025)]


def test_read_from_block_pipe_out_uses_dynamic_block_size():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    ops.read_from_block_pipe_out(0xA0, 16 * 1025)

    assert xem.block_pipe_out_calls == [(0xA0, 16, 16 * 1025)]


def test_read_from_pipe_out_raises_runtime_error_on_negative_return(monkeypatch):
    monkeypatch.setattr(fpga_components, "get_ok", lambda: FakeOk)
    ops = PipeOperations(FakePipeXem(read_error=-1))

    with pytest.raises(RuntimeError, match="Failed to read from pipe-out"):
        ops.read_from_pipe_out(0xA0, 16)


def test_read_from_block_pipe_out_raises_runtime_error_on_negative_return(
    monkeypatch,
):
    monkeypatch.setattr(fpga_components, "get_ok", lambda: FakeOk)
    xem = FakeBlockPipeXem(read_error=-2)
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    with pytest.raises(RuntimeError, match="Failed to read from block pipe-out"):
        ops.read_from_block_pipe_out(0xA0, 16)


def test_explicit_block_size_must_divide_transfer_byte():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    with pytest.raises(ValueError, match="integer multiple of block size"):
        ops.write_to_block_pipe_in(0x80, bytearray(16 * 1025), block_size=16384)

    assert xem.block_pipe_in_calls == []


def test_explicit_block_size_accepts_16_for_non_divisible_superspeed_size():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    ops.write_to_block_pipe_in(0x80, bytearray(16 * 1025), block_size=16)

    assert xem.block_pipe_in_calls == [(0x80, 16, 16 * 1025)]


def test_validate_block_size_requires_superspeed_power_of_two_range():
    validate_block_size(16, 16384, transfer_byte=16 * 1025)
    validate_block_size(16384, 16384, transfer_byte=16384 * 2)

    with pytest.raises(ValueError, match="between 16 and 16384"):
        validate_block_size(8, 16384)
    with pytest.raises(ValueError, match="power of 2"):
        validate_block_size(24, 16384)
    with pytest.raises(ValueError, match="multiple of 16"):
        validate_block_size(16, 16384, transfer_byte=18)


def test_validate_block_size_treats_zero_max_as_default_unknown_limit():
    validate_block_size(16, 0, transfer_byte=16 * 1025)
    validate_block_size(16384, 0, transfer_byte=16384 * 2)

    with pytest.raises(ValueError, match="between 16 and 16384"):
        validate_block_size(32768, 0)


def test_explicit_block_size_accepts_default_when_bt_max_blocksize_is_zero():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=0)

    ops.write_to_block_pipe_in(0x80, bytearray(16 * 1025), block_size=16)

    assert xem.block_pipe_in_calls == [(0x80, 16, 16 * 1025)]


def test_validate_block_size_accepts_usb2_full_speed_even_block_sizes():
    validate_block_size(
        24,
        64,
        transfer_byte=72,
        usb_speed="FULL",
        device_interface="USB 2",
    )

    with pytest.raises(ValueError, match="between 2 and 64"):
        validate_block_size(66, 64, usb_speed="FULL", device_interface="USB 2")
    with pytest.raises(ValueError, match="multiple of 2"):
        validate_block_size(3, 64, usb_speed="FULL", device_interface="USB 2")


def test_validate_block_size_accepts_usb2_high_speed_up_to_1024():
    validate_block_size(
        1000,
        1024,
        transfer_byte=3000,
        usb_speed="HIGH",
        device_interface="USB 2",
    )

    with pytest.raises(ValueError, match="between 2 and 1024"):
        validate_block_size(1026, 1024, usb_speed="HIGH", device_interface="USB 2")


def test_validate_block_size_uses_usb_speed_when_legacy_usb2_max_is_64():
    validate_block_size(
        1000,
        64,
        transfer_byte=3000,
        usb_speed="HIGH",
        device_interface="USB 2",
    )


def test_validate_block_size_caps_usb3_by_connection_speed():
    validate_block_size(64, 64, usb_speed="FULL", device_interface="USB 3")
    validate_block_size(1024, 1024, usb_speed="HIGH", device_interface="USB 3")

    with pytest.raises(ValueError, match="between 16 and 64"):
        validate_block_size(128, 64, usb_speed="FULL", device_interface="USB 3")
    with pytest.raises(ValueError, match="power of 2"):
        validate_block_size(24, 1024, usb_speed="HIGH", device_interface="USB 3")


def test_usb2_block_pipe_auto_selects_non_power_of_two_block_size():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(
        xem, bt_max_blocksize=64, usb_speed="HIGH", device_interface="USB 2"
    )

    ops.write_to_block_pipe_in(0x80, bytearray(1500))

    assert xem.block_pipe_in_calls == [(0x80, 750, 1500)]


def test_usb2_block_pipe_allows_two_byte_transfer_granularity():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(
        xem, bt_max_blocksize=64, usb_speed="FULL", device_interface="USB 2"
    )

    ops.write_to_block_pipe_in(0x80, bytearray(6), block_size=2)
    ops.read_from_block_pipe_out(0xA0, 6, block_size=2)

    assert xem.block_pipe_in_calls == [(0x80, 2, 6)]
    assert xem.block_pipe_out_calls == [(0xA0, 2, 6)]


def test_pcie_block_pipe_allows_eight_byte_transfer_without_block_size_constraint():
    validate_block_size(
        1024,
        1024,
        transfer_byte=8,
        usb_speed="SUPER",
        device_interface="PCIe",
    )


def test_pcie_block_pipe_auto_selects_eight_byte_transfer_granularity():
    xem = FakeBlockPipeXem()
    ops = BlockPipeOperations(
        xem, bt_max_blocksize=1024, usb_speed="SUPER", device_interface="PCIe"
    )

    ops.write_to_block_pipe_in(0x80, bytearray(8))
    ops.read_from_block_pipe_out(0xA0, 8)

    assert xem.block_pipe_in_calls == [(0x80, 8, 8)]
    assert xem.block_pipe_out_calls == [(0xA0, 8, 8)]


def test_pcie_block_pipe_requires_eight_byte_transfer_granularity():
    with pytest.raises(ValueError, match="multiple of 8"):
        validate_block_size(
            1024,
            1024,
            transfer_byte=4,
            usb_speed="SUPER",
            device_interface="PCIe",
        )


@pytest.mark.parametrize(
    "device_interface,usb_speed,expected_max",
    [
        (1, 1, 64),
        (1, 2, 1024),
        (2, 0, 1024),
        (3, 1, 64),
        (3, 2, 1024),
        (3, 3, 16384),
    ],
)
def test_fpga_config_uses_interface_and_usb_speed_for_block_pipe_max(
    device_interface, usb_speed, expected_max
):
    config = FPGAConfig.from_device_info(FakeDeviceInfo(device_interface, usb_speed))

    assert config.max_bt_blocksize == expected_max
