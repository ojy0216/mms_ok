"""Endpoint address constants used across FrontPanel operations.

The module exposes uppercase constants for new code and keeps the legacy
``Address`` namespace for backward compatibility.
"""

WIRE_IN_START = 0x00
WIRE_IN_END = 0x1F

WIRE_OUT_START = 0x20
WIRE_OUT_END = 0x3F

TRIGGER_IN_START = 0x40
TRIGGER_IN_END = 0x5F

TRIGGER_OUT_START = 0x60
TRIGGER_OUT_END = 0x7F

PIPE_IN_START = 0x80
PIPE_IN_END = 0x9F

PIPE_OUT_START = 0xA0
PIPE_OUT_END = 0xBF

BLOCK_PIPE_IN_START = 0x80
BLOCK_PIPE_IN_END = 0x9F

BLOCK_PIPE_OUT_START = 0xA0
BLOCK_PIPE_OUT_END = 0xBF


class Address:
    """Backward-compatible address namespace."""

    WIRE_IN_START = WIRE_IN_START
    WIRE_IN_END = WIRE_IN_END
    WIRE_OUT_START = WIRE_OUT_START
    WIRE_OUT_END = WIRE_OUT_END
    TRIGGER_IN_START = TRIGGER_IN_START
    TRIGGER_IN_END = TRIGGER_IN_END
    TRIGGER_OUT_START = TRIGGER_OUT_START
    TRIGGER_OUT_END = TRIGGER_OUT_END
    PIPE_IN_START = PIPE_IN_START
    PIPE_IN_END = PIPE_IN_END
    PIPE_OUT_START = PIPE_OUT_START
    PIPE_OUT_END = PIPE_OUT_END
    BLOCK_PIPE_IN_START = BLOCK_PIPE_IN_START
    BLOCK_PIPE_IN_END = BLOCK_PIPE_IN_END
    BLOCK_PIPE_OUT_START = BLOCK_PIPE_OUT_START
    BLOCK_PIPE_OUT_END = BLOCK_PIPE_OUT_END

    # Legacy attribute names preserved for existing callers.
    WireInStart = WIRE_IN_START
    WireInEnd = WIRE_IN_END
    WireOutStart = WIRE_OUT_START
    WireOutEnd = WIRE_OUT_END
    TriggerInStart = TRIGGER_IN_START
    TriggerInEnd = TRIGGER_IN_END
    TriggerOutStart = TRIGGER_OUT_START
    TriggerOutEnd = TRIGGER_OUT_END
    PipeInStart = PIPE_IN_START
    PipeInEnd = PIPE_IN_END
    PipeOutStart = PIPE_OUT_START
    PipeOutEnd = PIPE_OUT_END
    BlockPipeInStart = BLOCK_PIPE_IN_START
    BlockPipeInEnd = BLOCK_PIPE_IN_END
    BlockPipeOutStart = BLOCK_PIPE_OUT_START
    BlockPipeOutEnd = BLOCK_PIPE_OUT_END
