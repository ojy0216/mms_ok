from dataclasses import dataclass

@dataclass(frozen=True)
class Address:
    WireInStart = 0x00
    WireInEnd = 0x1F

    WireOutStart = 0x20
    WireOutEnd = 0x3F

    TriggerInStart = 0x40
    TriggerInEnd = 0x5F

    TriggerOutStart = 0x60
    TriggerOutEnd = 0x7F

    PipeInStart = 0x80
    PipeInEnd = 0x9F

    PipeOutStart = 0xA0
    PipeOutEnd = 0xBF

    BlockPipeInStart = 0x90
    BlockPipeInEnd = 0x9F

    BlockPipeOutStart = 0xA0
    BlockPipeOutEnd = 0xBF

    