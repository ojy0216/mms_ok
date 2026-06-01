from dataclasses import dataclass
from typing import Optional, Union

from .diagnostics import log_error


def _format_hex(value: int) -> str:
    return f"0x{value:X}"


def _validate_plain_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"{name} must be an integer, got {type(value).__name__}"
        log_error(message)
        raise TypeError(message)


def validate_address(address_start: int, address_end: int, address: int) -> None:
    _validate_plain_int("address_start", address_start)
    _validate_plain_int("address_end", address_end)
    _validate_plain_int("address", address)
    if address < address_start or address > address_end:
        message = (
            "Address must be between {} and {}, got {}".format(
                _format_hex(address_start),
                _format_hex(address_end),
                _format_hex(address),
            )
        )
        log_error(message)
        raise ValueError(message)


def validate_wire_value(value: int, num_bits: int) -> None:
    _validate_plain_int("value", value)
    _validate_plain_int("num_bits", num_bits)
    if value < 0 or value > (2**num_bits - 1):
        message = f"Value must be between 0 and {2**num_bits - 1}, got {value}"
        log_error(message)
        raise ValueError(message)


@dataclass(frozen=True)
class BlockPipeConstraints:
    min_block_size: int
    max_block_size: int
    block_size_multiple: int
    requires_power_of_two: bool
    uses_block_size: bool
    transfer_multiple: int
    description: str


@dataclass(frozen=True)
class BlockPipeTransportPolicy:
    max_block_size: int
    usb_speed: Optional[Union[int, str]] = None
    device_interface: Optional[Union[int, str]] = None

    def __post_init__(self) -> None:
        _validate_plain_int("max_block_size", self.max_block_size)

    @property
    def normalized_device_interface(self) -> str:
        return _normalize_device_interface(self.device_interface)

    @property
    def normalized_usb_speed(self) -> str:
        return _normalize_usb_speed(self.usb_speed)

    @property
    def device_max_block_size(self) -> int:
        interface = self.normalized_device_interface
        speed = self.normalized_usb_speed

        if interface == "USB2":
            return {"FULL": 64, "HIGH": 1024}.get(speed, 64)
        if interface == "PCIE":
            return 1024
        if interface == "USB3":
            return {"FULL": 64, "HIGH": 1024, "SUPER": 16384}.get(speed, 16384)
        return -1

    @property
    def effective_max_block_size(self) -> int:
        return self.constraints.max_block_size

    @property
    def constraints(self) -> BlockPipeConstraints:
        interface = self.normalized_device_interface
        speed = self.normalized_usb_speed

        if interface == "USB2":
            speed_max = {"FULL": 64, "HIGH": 1024}.get(speed)
            if speed_max is not None:
                max_allowed = speed_max
            elif self.max_block_size > 0:
                max_allowed = self.max_block_size
            else:
                max_allowed = 64
            return BlockPipeConstraints(
                min_block_size=2,
                max_block_size=max_allowed,
                block_size_multiple=2,
                requires_power_of_two=False,
                uses_block_size=True,
                transfer_multiple=2,
                description="USB 2.0 {}".format(speed.lower()),
            )

        if interface == "USB3":
            speed_max = {"FULL": 64, "HIGH": 1024, "SUPER": 16384}.get(speed)
            if speed_max is not None:
                max_allowed = speed_max
            elif self.max_block_size > 0:
                max_allowed = self.max_block_size
            else:
                max_allowed = 16384
            return BlockPipeConstraints(
                min_block_size=16,
                max_block_size=max_allowed,
                block_size_multiple=16,
                requires_power_of_two=True,
                uses_block_size=True,
                transfer_multiple=16,
                description="USB 3.0 {}".format(speed.lower()),
            )

        if interface == "PCIE":
            return BlockPipeConstraints(
                min_block_size=0,
                max_block_size=0,
                block_size_multiple=1,
                requires_power_of_two=False,
                uses_block_size=False,
                transfer_multiple=8,
                description="PCIe",
            )

        max_allowed = 16384 if self.max_block_size <= 0 else min(
            self.max_block_size, 16384
        )
        return BlockPipeConstraints(
            min_block_size=16,
            max_block_size=max_allowed,
            block_size_multiple=16,
            requires_power_of_two=True,
            uses_block_size=True,
            transfer_multiple=16,
            description="default",
        )

    @property
    def word_byte_width(self) -> int:
        return 2 if self.normalized_device_interface == "USB2" else 4

    def validate_block_size(
        self,
        block_size: Optional[int],
        transfer_byte: Optional[int] = None,
    ) -> None:
        if block_size is None:
            return
        _validate_plain_int("block_size", block_size)
        constraints = self.constraints

        if constraints.uses_block_size:
            if (
                block_size < constraints.min_block_size
                or block_size > constraints.max_block_size
            ):
                message = (
                    f"Block size must be between {constraints.min_block_size} "
                    f"and {constraints.max_block_size} bytes, "
                    f"got {block_size}"
                )
                log_error(message)
                raise ValueError(message)

            if constraints.requires_power_of_two and block_size & (block_size - 1):
                message = f"Block size must be a power of 2, got {block_size}"
                log_error(message)
                raise ValueError(message)

            if block_size % constraints.block_size_multiple != 0:
                message = (
                    f"Block size must be a multiple of "
                    f"{constraints.block_size_multiple}, got {block_size}"
                )
                log_error(message)
                raise ValueError(message)

        if transfer_byte is None:
            return

        _validate_plain_int("transfer_byte", transfer_byte)
        if transfer_byte % constraints.transfer_multiple != 0:
            message = (
                f"Transfer byte must be a multiple of "
                f"{constraints.transfer_multiple}, got {transfer_byte}"
            )
            log_error(message)
            raise ValueError(message)
        if constraints.uses_block_size and transfer_byte % block_size != 0:
            message = (
                f"Transfer byte must be an integer multiple of block size, "
                f"got transfer_byte={transfer_byte}, block_size={block_size}"
            )
            log_error(message)
            raise ValueError(message)

    def select_block_size(self, transfer_byte: int) -> int:
        _validate_plain_int("transfer_byte", transfer_byte)
        constraints = self.constraints

        if not constraints.uses_block_size:
            if transfer_byte % constraints.transfer_multiple != 0:
                self._raise_transfer_multiple_error(transfer_byte, constraints)
            return constraints.transfer_multiple

        max_block_size = constraints.max_block_size
        if transfer_byte > 0:
            max_block_size = min(max_block_size, transfer_byte)

        if constraints.requires_power_of_two:
            block_size = 1 << (max_block_size.bit_length() - 1)
            while block_size >= constraints.min_block_size:
                if transfer_byte % block_size == 0:
                    return block_size
                block_size //= 2
        else:
            block_size = max_block_size - (
                max_block_size % constraints.block_size_multiple
            )
            while block_size >= constraints.min_block_size:
                if transfer_byte % block_size == 0:
                    return block_size
                block_size -= constraints.block_size_multiple

        if transfer_byte % constraints.transfer_multiple != 0:
            self._raise_transfer_multiple_error(transfer_byte, constraints)

        message = (
            f"Transfer byte must be an integer multiple of a valid block size, "
            f"got {transfer_byte}"
        )
        log_error(message)
        raise ValueError(message)

    @staticmethod
    def _raise_transfer_multiple_error(
        transfer_byte: int, constraints: BlockPipeConstraints
    ) -> None:
        message = (
            f"Transfer byte must be a multiple of "
            f"{constraints.transfer_multiple} for "
            f"{constraints.description} block pipes, got {transfer_byte}"
        )
        log_error(message)
        raise ValueError(message)


def _normalize_device_interface(device_interface: Optional[Union[int, str]]) -> str:
    if device_interface is None:
        return "UNKNOWN"
    if isinstance(device_interface, int):
        return {1: "USB2", 2: "PCIE", 3: "USB3"}.get(device_interface, "UNKNOWN")
    value = str(device_interface).upper().replace(" ", "").replace(".", "")
    if value in {"USB2", "USB20"}:
        return "USB2"
    if value in {"USB3", "USB30"}:
        return "USB3"
    if value in {"PCI", "PCIE", "PCIEXPRESS"}:
        return "PCIE"
    return "UNKNOWN"


def _normalize_usb_speed(usb_speed: Optional[Union[int, str]]) -> str:
    if usb_speed is None:
        return "UNKNOWN"
    if isinstance(usb_speed, int):
        return {1: "FULL", 2: "HIGH", 3: "SUPER"}.get(usb_speed, "UNKNOWN")
    return str(usb_speed).upper().replace(" ", "_")


def get_block_pipe_constraints(
    max_block_size: int,
    usb_speed: Optional[Union[int, str]] = None,
    device_interface: Optional[Union[int, str]] = None,
) -> BlockPipeConstraints:
    return BlockPipeTransportPolicy(
        max_block_size, usb_speed=usb_speed, device_interface=device_interface
    ).constraints


def validate_block_size(
    block_size: int,
    max_block_size: int,
    transfer_byte: Optional[int] = None,
    usb_speed: Optional[Union[int, str]] = None,
    device_interface: Optional[Union[int, str]] = None,
) -> None:
    BlockPipeTransportPolicy(
        max_block_size, usb_speed=usb_speed, device_interface=device_interface
    ).validate_block_size(block_size, transfer_byte)
