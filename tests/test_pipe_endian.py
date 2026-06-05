from __future__ import annotations

import inspect
from typing import Optional

import numpy as np
import pytest
from loguru import logger

from mms_ok.fpga_base import XEM
from mms_ok.fpga_components import (
    REORDER_STR_WARNING,
    BlockPipeOperations,
    PipeOperations,
)
from mms_ok.pipeoutdata import PipeOutData


def capture_warning_messages(call):
    messages = []
    sink_id = logger.add(
        lambda message: messages.append(message.record["message"]),
        level="WARNING",
    )
    try:
        call()
    finally:
        logger.remove(sink_id)
    return messages


def capture_debug_messages(call):
    messages = []
    sink_id = logger.add(
        lambda message: messages.append(message.record["message"]),
        level="DEBUG",
    )
    try:
        call()
    finally:
        logger.remove(sink_id)
    return messages


class CapturingPipeXem:
    def __init__(self, read_data: Optional[bytes] = None) -> None:
        self.pipe_in_calls = []
        self.read_data = read_data

    def WriteToPipeIn(self, ep_addr, data):
        self.pipe_in_calls.append((ep_addr, bytes(data)))
        return len(data)

    def ReadFromPipeOut(self, ep_addr, data):
        if self.read_data is not None:
            data[: len(self.read_data)] = self.read_data
            return len(self.read_data)
        return len(data)


class CapturingBlockPipeXem:
    def __init__(self, read_data: Optional[bytes] = None) -> None:
        self.block_pipe_in_calls = []
        self.block_pipe_out_calls = []
        self.read_data = read_data

    def WriteToBlockPipeIn(self, ep_addr, block_size, data):
        self.block_pipe_in_calls.append((ep_addr, block_size, bytes(data)))
        return len(data)

    def ReadFromBlockPipeOut(self, ep_addr, block_size, data):
        self.block_pipe_out_calls.append((ep_addr, block_size, len(data)))
        if self.read_data is not None:
            data[: len(self.read_data)] = self.read_data
            return len(self.read_data)
        return len(data)


class EndpointXEM(XEM):
    def __init__(self, pipe_ops=None, block_pipe_ops=None) -> None:
        self.pipe_ops = pipe_ops
        self.block_pipe_ops = block_pipe_ops
        self.verbose_level = 0

    def _check_device_settings(self) -> None:
        pass

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        pass


@pytest.mark.parametrize(
    ("owner", "method_name"),
    [
        (PipeOperations, "write_to_pipe_in"),
        (PipeOperations, "read_from_pipe_out"),
        (BlockPipeOperations, "write_to_block_pipe_in"),
        (BlockPipeOperations, "read_from_block_pipe_out"),
        (XEM, "WriteToPipeIn"),
        (XEM, "ReadFromPipeOut"),
        (XEM, "WriteToBlockPipeIn"),
        (XEM, "ReadFromBlockPipeOut"),
    ],
)
def test_pipe_methods_keep_endian_before_reorder_str(owner, method_name):
    signature = inspect.signature(getattr(owner, method_name))
    parameters = list(signature.parameters)

    assert parameters.index("endian") + 1 == parameters.index("reorder_str")
    assert parameters.index("reorder_str") + 1 == parameters.index("reverse")
    assert signature.parameters["reverse"].kind is inspect.Parameter.KEYWORD_ONLY
    if method_name in {
        "write_to_pipe_in",
        "write_to_block_pipe_in",
        "WriteToPipeIn",
        "WriteToBlockPipeIn",
    }:
        assert parameters.index("reverse") + 1 == parameters.index("verbose")
        assert signature.parameters["verbose"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["verbose"].default is False


def test_write_to_pipe_in_hex_defaults_to_little_endian_words():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    ops.write_to_pipe_in(0x80, "AABBCCDD11223344556677889900A1B2")

    assert xem.pipe_in_calls == [
        (
            0x80,
            bytes.fromhex("DDCCBBAA4433221188776655B2A10099"),
        )
    ]


def test_write_to_pipe_in_hex_accepts_big_endian_words():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    ops.write_to_pipe_in(
        0x80, "AABBCCDD11223344556677889900A1B2", endian="big"
    )

    assert xem.pipe_in_calls == [
        (
            0x80,
            bytes.fromhex("AABBCCDD11223344556677889900A1B2"),
        )
    ]


def test_write_to_pipe_in_hex_big_endian_accepts_fromhex_whitespace():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    ops.write_to_pipe_in(
        0x80,
        "AA BB CC DD 11 22 33 44 55 66 77 88 99 00 A1 B2",
        endian="big",
    )

    assert xem.pipe_in_calls == [
        (
            0x80,
            bytes.fromhex("AABBCCDD11223344556677889900A1B2"),
        )
    ]


def test_write_to_pipe_in_hex_accepts_little_endian_words():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    ops.write_to_pipe_in(
        0x80, "AABBCCDD11223344556677889900A1B2", endian="little"
    )

    assert xem.pipe_in_calls == [
        (
            0x80,
            bytes.fromhex("DDCCBBAA4433221188776655B2A10099"),
        )
    ]


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, "B2A100998877665544332211DDCCBBAA"),
        ({"endian": "little"}, "B2A100998877665544332211DDCCBBAA"),
        ({"endian": "big"}, "9900A1B25566778811223344AABBCCDD"),
    ],
)
def test_write_to_pipe_in_hex_reverse_reverses_word_order(kwargs, expected):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    ops.write_to_pipe_in(
        0x80, "AABBCCDD11223344556677889900A1B2", reverse=True, **kwargs
    )

    assert xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]


def test_write_to_pipe_in_verbose_logs_payload_per_pipe_cycle():
    expected = "DDCCBBAA4433221188776655B2A10099"
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_debug_messages(
        lambda: ops.write_to_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            verbose=True,
        )
    )

    assert xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]
    assert any("WriteToPipeIn" in message for message in messages)
    assert any("0x80" in message for message in messages)
    assert any("32-bit/cycle" in message for message in messages)
    assert not any(expected in message for message in messages)
    for cycle, payload in enumerate(["DDCCBBAA", "44332211", "88776655", "B2A10099"]):
        assert any(
            f"cycle {cycle}" in message and f"32-bit payload: {payload}" in message
            for message in messages
        )


def test_write_to_pipe_in_verbose_false_does_not_log_payload():
    expected = "DDCCBBAA4433221188776655B2A10099"
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_debug_messages(
        lambda: ops.write_to_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
        )
    )

    assert xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]
    assert not any(expected in message for message in messages)


@pytest.mark.parametrize(
    "endian,reorder_str,expected",
    [
        ("big", True, "AABBCCDD11223344556677889900A1B2"),
        ("big", False, "AABBCCDD11223344556677889900A1B2"),
        ("little", True, "DDCCBBAA4433221188776655B2A10099"),
        ("little", False, "DDCCBBAA4433221188776655B2A10099"),
    ],
)
def test_write_to_pipe_in_explicit_endian_overrides_reorder_str(
    endian, reorder_str, expected
):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_warning_messages(
        lambda: ops.write_to_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            endian=endian,
            reorder_str=reorder_str,
        )
    )

    assert REORDER_STR_WARNING in messages
    assert xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]


@pytest.mark.parametrize(
    "reorder_str,expected",
    [
        (False, "AABBCCDD11223344556677889900A1B2"),
        (True, "DDCCBBAA4433221188776655B2A10099"),
    ],
)
def test_write_to_pipe_in_keyword_reorder_str_without_endian_uses_legacy_order(
    reorder_str, expected
):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_warning_messages(
        lambda: ops.write_to_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            reorder_str=reorder_str,
        )
    )

    assert REORDER_STR_WARNING in messages
    assert xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]


def test_write_to_pipe_in_legacy_no_reorder_accepts_fromhex_whitespace():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_warning_messages(
        lambda: ops.write_to_pipe_in(
            0x80,
            "AA BB CC DD 11 22 33 44 55 66 77 88 99 00 A1 B2",
            reorder_str=False,
        )
    )

    assert REORDER_STR_WARNING in messages
    assert xem.pipe_in_calls == [
        (0x80, bytes.fromhex("AABBCCDD11223344556677889900A1B2"))
    ]


def test_read_from_pipe_out_hex_defaults_to_little_endian_words():
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )

    result = ops.read_from_pipe_out(0xA0, 16)

    assert result.raw_data == bytearray.fromhex(
        "DDCCBBAA4433221188776655B2A10099"
    )
    assert result.hex_data == "AABBCCDD11223344556677889900A1B2"


def test_read_from_pipe_out_hex_accepts_big_endian_words():
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )

    result = ops.read_from_pipe_out(0xA0, 16, endian="big")

    assert result.hex_data == "DDCCBBAA4433221188776655B2A10099"


def test_read_from_pipe_out_hex_accepts_little_endian_words():
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )

    result = ops.read_from_pipe_out(0xA0, 16, endian="little")

    assert result.hex_data == "AABBCCDD11223344556677889900A1B2"


def test_read_from_pipe_out_reverse_reverses_hex_32_bit_words_only():
    raw = bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    ops = PipeOperations(CapturingPipeXem(raw))
    buffer = bytearray(16)

    result = ops.read_from_pipe_out(0xA0, buffer, reverse=True)

    assert result.raw_data is buffer
    assert result.raw_data == bytearray(raw)
    assert result.hex_data == "9900A1B25566778811223344AABBCCDD"


def test_read_from_pipe_out_big_endian_reverse_reverses_hex_32_bit_words_only():
    raw = bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    ops = PipeOperations(CapturingPipeXem(raw))

    result = ops.read_from_pipe_out(0xA0, 16, endian="big", reverse=True)

    assert result.raw_data == bytearray(raw)
    assert result.hex_data == "B2A100998877665544332211DDCCBBAA"


def test_pipe_out_data_default_keeps_little_endian_without_warning():
    raw = bytearray.fromhex("DDCCBBAA4433221188776655B2A10099")
    result = None

    def build():
        nonlocal result
        result = PipeOutData(4, raw)

    messages = capture_warning_messages(build)

    assert REORDER_STR_WARNING not in messages
    assert result is not None
    assert result.hex_data == "AABBCCDD11223344556677889900A1B2"


@pytest.mark.parametrize(
    "reorder_str,expected",
    [
        (False, "DDCCBBAA4433221188776655B2A10099"),
        (True, "AABBCCDD11223344556677889900A1B2"),
    ],
)
def test_pipe_out_data_positional_reorder_str_warns_and_uses_legacy_order(
    reorder_str, expected
):
    raw = bytearray.fromhex("DDCCBBAA4433221188776655B2A10099")
    result = None

    def build():
        nonlocal result
        result = PipeOutData(4, raw, reorder_str)

    messages = capture_warning_messages(build)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == expected


@pytest.mark.parametrize(
    "endian,reorder_str,expected",
    [
        ("big", True, "DDCCBBAA4433221188776655B2A10099"),
        ("big", False, "DDCCBBAA4433221188776655B2A10099"),
        ("little", True, "AABBCCDD11223344556677889900A1B2"),
        ("little", False, "AABBCCDD11223344556677889900A1B2"),
    ],
)
def test_pipe_out_data_explicit_endian_overrides_reorder_str(
    endian, reorder_str, expected
):
    raw = bytearray.fromhex("DDCCBBAA4433221188776655B2A10099")
    result = None

    def build():
        nonlocal result
        result = PipeOutData(4, raw, reorder_str=reorder_str, endian=endian)

    messages = capture_warning_messages(build)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == expected


def test_pipe_out_data_explicit_endian_overrides_reorder_str_with_reverse():
    raw = bytearray.fromhex("DDCCBBAA4433221188776655B2A10099")
    result = None

    def build():
        nonlocal result
        result = PipeOutData(
            4,
            raw,
            reorder_str=True,
            endian="big",
            reverse=True,
        )

    messages = capture_warning_messages(build)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.raw_data == raw
    assert result.hex_data == "B2A100998877665544332211DDCCBBAA"


@pytest.mark.parametrize(
    "endian,reorder_str,expected",
    [
        ("big", True, "DDCCBBAA4433221188776655B2A10099"),
        ("big", False, "DDCCBBAA4433221188776655B2A10099"),
        ("little", True, "AABBCCDD11223344556677889900A1B2"),
        ("little", False, "AABBCCDD11223344556677889900A1B2"),
    ],
)
def test_read_from_pipe_out_explicit_endian_overrides_reorder_str(
    endian, reorder_str, expected
):
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )

    result = None

    def read():
        nonlocal result
        result = ops.read_from_pipe_out(
            0xA0,
            16,
            endian=endian,
            reorder_str=reorder_str,
        )

    messages = capture_warning_messages(read)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == expected


@pytest.mark.parametrize(
    "reorder_str,expected",
    [
        (False, "DDCCBBAA4433221188776655B2A10099"),
        (True, "AABBCCDD11223344556677889900A1B2"),
    ],
)
def test_read_from_pipe_out_keyword_reorder_str_without_endian_uses_legacy_order(
    reorder_str, expected
):
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )
    result = None

    def read():
        nonlocal result
        result = ops.read_from_pipe_out(
            0xA0,
            16,
            reorder_str=reorder_str,
        )

    messages = capture_warning_messages(read)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == expected


def test_read_from_pipe_out_reorder_str_warning_still_applies_with_reverse():
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )
    result = None

    def read():
        nonlocal result
        result = ops.read_from_pipe_out(
            0xA0,
            16,
            reorder_str=False,
            reverse=True,
        )

    messages = capture_warning_messages(read)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == "B2A100998877665544332211DDCCBBAA"


@pytest.mark.parametrize(
    "legacy_reorder,expected",
    [
        (False, "AABBCCDD11223344556677889900A1B2"),
        (True, "DDCCBBAA4433221188776655B2A10099"),
    ],
)
def test_positional_boolean_pipe_in_warns_and_uses_legacy_order(
    legacy_reorder, expected
):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_warning_messages(
        lambda: ops.write_to_pipe_in(
            0x80, "AABBCCDD11223344556677889900A1B2", legacy_reorder
        )
    )

    assert REORDER_STR_WARNING in messages
    assert xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]


@pytest.mark.parametrize(
    "legacy_reorder,expected",
    [
        (False, "DDCCBBAA4433221188776655B2A10099"),
        (True, "AABBCCDD11223344556677889900A1B2"),
    ],
)
def test_positional_boolean_pipe_out_warns_and_uses_legacy_order(
    legacy_reorder, expected
):
    ops = PipeOperations(
        CapturingPipeXem(bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    )
    result = None

    def read():
        nonlocal result
        result = ops.read_from_pipe_out(0xA0, 16, legacy_reorder)

    messages = capture_warning_messages(read)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == expected


def test_endian_big_does_not_emit_reorder_str_warning():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)

    messages = capture_warning_messages(
        lambda: ops.write_to_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            endian="big",
        )
    )

    assert REORDER_STR_WARNING not in messages
    assert xem.pipe_in_calls == [
        (0x80, bytes.fromhex("AABBCCDD11223344556677889900A1B2"))
    ]


def test_block_pipe_hex_usb2_uses_two_byte_words():
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(
        xem, bt_max_blocksize=64, usb_speed="FULL", device_interface="USB 2"
    )

    ops.write_to_block_pipe_in(0x80, "AABBCCDD", block_size=2)
    result = ops.read_from_block_pipe_out(
        0xA0, bytearray.fromhex("BBAADDCC"), block_size=2
    )

    assert xem.block_pipe_in_calls == [(0x80, 2, bytes.fromhex("BBAADDCC"))]
    assert result.hex_data == "AABBCCDD"


def test_block_pipe_hex_usb3_uses_four_byte_words():
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    ops.write_to_block_pipe_in(0x80, "AABBCCDD11223344556677889900A1B2")
    result = ops.read_from_block_pipe_out(
        0xA0,
        bytearray.fromhex("DDCCBBAA4433221188776655B2A10099"),
    )

    assert xem.block_pipe_in_calls == [
        (0x80, 16, bytes.fromhex("DDCCBBAA4433221188776655B2A10099"))
    ]
    assert result.hex_data == "AABBCCDD11223344556677889900A1B2"


def test_read_from_block_pipe_out_usb3_reverse_reverses_hex_32_bit_words_only():
    raw = bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    ops = BlockPipeOperations(CapturingBlockPipeXem(raw), bt_max_blocksize=16384)
    buffer = bytearray(16)

    result = ops.read_from_block_pipe_out(0xA0, buffer, reverse=True)

    assert result.raw_data is buffer
    assert result.raw_data == bytearray(raw)
    assert result.hex_data == "9900A1B25566778811223344AABBCCDD"


def test_read_from_block_pipe_out_usb2_reverse_uses_32_bit_hex_words():
    raw = bytes.fromhex("BBAADDCC22114433")
    ops = BlockPipeOperations(
        CapturingBlockPipeXem(raw),
        bt_max_blocksize=64,
        usb_speed="FULL",
        device_interface="USB 2",
    )

    result = ops.read_from_block_pipe_out(0xA0, 8, block_size=2, reverse=True)

    assert result.raw_data == bytearray(raw)
    assert result.hex_data == "11223344AABBCCDD"


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, "B2A100998877665544332211DDCCBBAA"),
        ({"endian": "little"}, "B2A100998877665544332211DDCCBBAA"),
        ({"endian": "big"}, "9900A1B25566778811223344AABBCCDD"),
    ],
)
def test_write_to_block_pipe_in_hex_reverse_reverses_word_order(kwargs, expected):
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    ops.write_to_block_pipe_in(
        0x80, "AABBCCDD11223344556677889900A1B2", reverse=True, **kwargs
    )

    assert xem.block_pipe_in_calls == [(0x80, 16, bytes.fromhex(expected))]


def test_write_to_block_pipe_in_verbose_logs_usb3_payload_per_pipe_cycle_and_block_size():
    expected = "B2A100998877665544332211DDCCBBAA"
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    messages = capture_debug_messages(
        lambda: ops.write_to_block_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            reverse=True,
            verbose=True,
        )
    )

    assert xem.block_pipe_in_calls == [(0x80, 16, bytes.fromhex(expected))]
    assert any("WriteToBlockPipeIn" in message for message in messages)
    assert any("0x80" in message for message in messages)
    assert any("block_size=16" in message for message in messages)
    assert any("32-bit/cycle" in message for message in messages)
    assert not any(expected in message for message in messages)
    for cycle, payload in enumerate(["B2A10099", "88776655", "44332211", "DDCCBBAA"]):
        assert any(
            f"cycle {cycle}" in message and f"32-bit payload: {payload}" in message
            for message in messages
        )


def test_write_to_block_pipe_in_verbose_logs_usb2_payload_per_pipe_cycle():
    expected = "BBAADDCC"
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(
        xem, bt_max_blocksize=64, usb_speed="FULL", device_interface="USB 2"
    )

    messages = capture_debug_messages(
        lambda: ops.write_to_block_pipe_in(
            0x80,
            "AABBCCDD",
            block_size=2,
            verbose=True,
        )
    )

    assert xem.block_pipe_in_calls == [(0x80, 2, bytes.fromhex(expected))]
    assert any("16-bit/cycle" in message for message in messages)
    assert not any(expected in message for message in messages)
    for cycle, payload in enumerate(["BBAA", "DDCC"]):
        assert any(
            f"cycle {cycle}" in message and f"16-bit payload: {payload}" in message
            for message in messages
        )


def test_write_to_block_pipe_in_hex_reverse_uses_32_bit_words_for_usb2():
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(
        xem, bt_max_blocksize=64, usb_speed="FULL", device_interface="USB 2"
    )

    ops.write_to_block_pipe_in(0x80, "AABBCCDD11223344", block_size=2, reverse=True)

    assert xem.block_pipe_in_calls == [(0x80, 2, bytes.fromhex("22114433BBAADDCC"))]


def test_block_pipe_explicit_endian_overrides_reorder_str():
    xem = CapturingBlockPipeXem(
        bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    )
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)
    result = None

    def transfer():
        nonlocal result
        ops.write_to_block_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            endian="big",
            reorder_str=True,
        )
        result = ops.read_from_block_pipe_out(
            0xA0,
            16,
            endian="big",
            reorder_str=False,
        )

    messages = capture_warning_messages(transfer)

    assert messages.count(REORDER_STR_WARNING) == 2
    assert xem.block_pipe_in_calls == [
        (0x80, 16, bytes.fromhex("AABBCCDD11223344556677889900A1B2"))
    ]
    assert result is not None
    assert result.hex_data == "DDCCBBAA4433221188776655B2A10099"


def test_block_pipe_in_keyword_reorder_str_false_without_endian_uses_big_endian():
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)

    messages = capture_warning_messages(
        lambda: ops.write_to_block_pipe_in(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            reorder_str=False,
        )
    )

    assert REORDER_STR_WARNING in messages
    assert xem.block_pipe_in_calls == [
        (0x80, 16, bytes.fromhex("AABBCCDD11223344556677889900A1B2"))
    ]


def test_block_pipe_out_keyword_reorder_str_false_without_endian_uses_big_endian():
    ops = BlockPipeOperations(
        CapturingBlockPipeXem(
            bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
        ),
        bt_max_blocksize=16384,
    )
    result = None

    def read():
        nonlocal result
        result = ops.read_from_block_pipe_out(
            0xA0,
            16,
            reorder_str=False,
        )

    messages = capture_warning_messages(read)

    assert REORDER_STR_WARNING in messages
    assert result is not None
    assert result.hex_data == "DDCCBBAA4433221188776655B2A10099"


def test_xem_pipe_wrappers_preserve_keyword_reorder_str_false_legacy_order():
    pipe_xem = CapturingPipeXem(
        bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    )
    fpga = EndpointXEM(pipe_ops=PipeOperations(pipe_xem))
    result = None

    def transfer():
        nonlocal result
        fpga.WriteToPipeIn(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            reorder_str=False,
        )
        result = fpga.ReadFromPipeOut(0xA0, 16, reorder_str=False)

    messages = capture_warning_messages(transfer)

    assert messages.count(REORDER_STR_WARNING) == 2
    assert pipe_xem.pipe_in_calls == [
        (0x80, bytes.fromhex("AABBCCDD11223344556677889900A1B2"))
    ]
    assert result is not None
    assert result.hex_data == "DDCCBBAA4433221188776655B2A10099"


def test_xem_pipe_wrapper_passes_reverse_to_write():
    pipe_xem = CapturingPipeXem()
    fpga = EndpointXEM(pipe_ops=PipeOperations(pipe_xem))

    fpga.WriteToPipeIn(0x80, "AABBCCDD11223344556677889900A1B2", reverse=True)

    assert pipe_xem.pipe_in_calls == [
        (0x80, bytes.fromhex("B2A100998877665544332211DDCCBBAA"))
    ]


def test_xem_pipe_wrapper_passes_verbose_to_write():
    expected = "DDCCBBAA4433221188776655B2A10099"
    pipe_xem = CapturingPipeXem()
    fpga = EndpointXEM(pipe_ops=PipeOperations(pipe_xem))

    messages = capture_debug_messages(
        lambda: fpga.WriteToPipeIn(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            verbose=True,
        )
    )

    assert pipe_xem.pipe_in_calls == [(0x80, bytes.fromhex(expected))]
    assert not any(expected in message for message in messages)
    assert any("WriteToPipeIn" in message for message in messages)
    assert any("32-bit/cycle" in message for message in messages)
    for cycle, payload in enumerate(["DDCCBBAA", "44332211", "88776655", "B2A10099"]):
        assert any(
            f"cycle {cycle}" in message and f"32-bit payload: {payload}" in message
            for message in messages
        )


def test_xem_pipe_wrapper_passes_reverse_to_read():
    pipe_xem = CapturingPipeXem(
        bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    )
    fpga = EndpointXEM(pipe_ops=PipeOperations(pipe_xem))

    result = fpga.ReadFromPipeOut(0xA0, 16, reverse=True)

    assert result.hex_data == "9900A1B25566778811223344AABBCCDD"


def test_xem_block_pipe_wrappers_preserve_keyword_reorder_str_false_legacy_order():
    block_xem = CapturingBlockPipeXem(
        bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    )
    fpga = EndpointXEM(
        block_pipe_ops=BlockPipeOperations(block_xem, bt_max_blocksize=16384)
    )
    result = None

    def transfer():
        nonlocal result
        fpga.WriteToBlockPipeIn(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            reorder_str=False,
        )
        result = fpga.ReadFromBlockPipeOut(0xA0, 16, reorder_str=False)

    messages = capture_warning_messages(transfer)

    assert messages.count(REORDER_STR_WARNING) == 2
    assert block_xem.block_pipe_in_calls == [
        (0x80, 16, bytes.fromhex("AABBCCDD11223344556677889900A1B2"))
    ]
    assert result is not None
    assert result.hex_data == "DDCCBBAA4433221188776655B2A10099"


def test_xem_block_pipe_wrapper_passes_reverse_to_write():
    block_xem = CapturingBlockPipeXem()
    fpga = EndpointXEM(
        block_pipe_ops=BlockPipeOperations(block_xem, bt_max_blocksize=16384)
    )

    fpga.WriteToBlockPipeIn(
        0x80, "AABBCCDD11223344556677889900A1B2", reverse=True
    )

    assert block_xem.block_pipe_in_calls == [
        (0x80, 16, bytes.fromhex("B2A100998877665544332211DDCCBBAA"))
    ]


def test_xem_block_pipe_wrapper_passes_verbose_to_write():
    expected = "DDCCBBAA4433221188776655B2A10099"
    block_xem = CapturingBlockPipeXem()
    fpga = EndpointXEM(
        block_pipe_ops=BlockPipeOperations(block_xem, bt_max_blocksize=16384)
    )

    messages = capture_debug_messages(
        lambda: fpga.WriteToBlockPipeIn(
            0x80,
            "AABBCCDD11223344556677889900A1B2",
            verbose=True,
        )
    )

    assert block_xem.block_pipe_in_calls == [(0x80, 16, bytes.fromhex(expected))]
    assert not any(expected in message for message in messages)
    assert any(
        "WriteToBlockPipeIn" in message and "block_size=16" in message
        for message in messages
    )
    assert any("32-bit/cycle" in message for message in messages)
    for cycle, payload in enumerate(["DDCCBBAA", "44332211", "88776655", "B2A10099"]):
        assert any(
            f"cycle {cycle}" in message and f"32-bit payload: {payload}" in message
            for message in messages
        )


def test_xem_block_pipe_wrapper_passes_reverse_to_read():
    block_xem = CapturingBlockPipeXem(
        bytes.fromhex("DDCCBBAA4433221188776655B2A10099")
    )
    fpga = EndpointXEM(
        block_pipe_ops=BlockPipeOperations(block_xem, bt_max_blocksize=16384)
    )

    result = fpga.ReadFromBlockPipeOut(0xA0, 16, reverse=True)

    assert result.hex_data == "9900A1B25566778811223344AABBCCDD"


@pytest.mark.parametrize(
    "dtype,values",
    [
        (np.uint16, [0x1122] * 8),
        (np.uint32, [0x11223344] * 4),
        (np.uint64, [0x1122334455667788] * 2),
        (np.int16, [-2, 0x1234] * 4),
    ],
)
@pytest.mark.parametrize("endian", ["little", "big"])
def test_write_to_pipe_in_numpy_integer_arrays_use_requested_endian(
    dtype, values, endian
):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)
    samples = np.array(values, dtype=dtype)
    signed = np.issubdtype(samples.dtype, np.signedinteger)
    expected = b"".join(
        int(value).to_bytes(samples.dtype.itemsize, endian, signed=signed)
        for value in samples
    )

    ops.write_to_pipe_in(0x80, samples, endian=endian)

    assert xem.pipe_in_calls == [(0x80, expected)]


@pytest.mark.parametrize(
    "dtype,endian",
    [
        (">i2", "little"),
        ("<i2", "big"),
    ],
)
def test_write_to_pipe_in_numpy_integer_arrays_follow_requested_endian_not_dtype(
    dtype, endian
):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)
    samples = np.array([-2, 0x1234] * 4, dtype=np.dtype(dtype))
    expected = b"".join(
        int(value).to_bytes(samples.dtype.itemsize, endian, signed=True)
        for value in samples
    )

    ops.write_to_pipe_in(0x80, samples, endian=endian)

    assert xem.pipe_in_calls == [(0x80, expected)]


def test_write_to_pipe_in_numpy_non_integer_arrays_keep_raw_bytes():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)
    samples = np.array([1.5, 2.5], dtype=np.float64)

    ops.write_to_pipe_in(0x80, samples, endian="big")

    assert xem.pipe_in_calls == [(0x80, np.ascontiguousarray(samples).tobytes())]


@pytest.mark.parametrize("endian", ["little", "big"])
def test_write_to_pipe_in_numpy_integer_reverse_reverses_elements(endian):
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)
    samples = np.array([0x1122, 0x3344, 0x5566, 0x7788] * 2, dtype=np.uint16)
    expected = b"".join(
        int(value).to_bytes(samples.dtype.itemsize, endian, signed=False)
        for value in samples[::-1]
    )

    ops.write_to_pipe_in(0x80, samples, endian=endian, reverse=True)

    assert xem.pipe_in_calls == [(0x80, expected)]


@pytest.mark.parametrize("endian", ["little", "big"])
def test_write_to_block_pipe_in_numpy_integer_reverse_reverses_elements(endian):
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)
    samples = np.array([0x11223344, 0x55667788, 0x9900A1B2, 0xCCDDEEFF], dtype=np.uint32)
    expected = b"".join(
        int(value).to_bytes(samples.dtype.itemsize, endian, signed=False)
        for value in samples[::-1]
    )

    ops.write_to_block_pipe_in(0x80, samples, endian=endian, reverse=True)

    assert xem.block_pipe_in_calls == [(0x80, 16, expected)]


def test_write_to_pipe_in_numpy_non_integer_reverse_reverses_elements_only():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)
    samples = np.array([[1.5, 2.5], [3.5, 4.5]], dtype=np.float64)
    expected = np.ascontiguousarray(np.ravel(samples, order="C")[::-1]).tobytes()

    ops.write_to_pipe_in(0x80, samples, endian="big", reverse=True)

    assert xem.pipe_in_calls == [(0x80, expected)]


def test_write_to_block_pipe_in_numpy_non_integer_reverse_reverses_elements_only():
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)
    samples = np.array([1.5, 2.5], dtype=np.float64)
    expected = np.ascontiguousarray(samples[::-1]).tobytes()

    ops.write_to_block_pipe_in(0x80, samples, endian="big", reverse=True)

    assert xem.block_pipe_in_calls == [(0x80, 16, expected)]


def test_write_to_pipe_in_bytearray_reverse_leaves_buffer_unchanged():
    xem = CapturingPipeXem()
    ops = PipeOperations(xem)
    data = bytearray.fromhex("00112233445566778899AABBCCDDEEFF")

    ops.write_to_pipe_in(0x80, data, reverse=True)

    assert xem.pipe_in_calls == [(0x80, bytes(data))]


def test_write_to_block_pipe_in_bytearray_reverse_leaves_buffer_unchanged():
    xem = CapturingBlockPipeXem()
    ops = BlockPipeOperations(xem, bt_max_blocksize=16384)
    data = bytearray.fromhex("00112233445566778899AABBCCDDEEFF")

    ops.write_to_block_pipe_in(0x80, data, reverse=True)

    assert xem.block_pipe_in_calls == [(0x80, 16, bytes(data))]


def test_pipe_operations_reject_invalid_endian():
    ops = PipeOperations(CapturingPipeXem())

    with pytest.raises(ValueError, match="endian"):
        ops.write_to_pipe_in(0x80, bytearray(16), endian="middle")
