from loguru import logger


def _validate_plain_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        logger.error(f"{name} must be an integer, got {type(value).__name__}")
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")


def validate_address(address_start: int, address_end: int, address: int) -> None:
    _validate_plain_int("address_start", address_start)
    _validate_plain_int("address_end", address_end)
    _validate_plain_int("address", address)
    if address < address_start or address > address_end:
        logger.error(
            f"Address must be between {address_start} and {address_end}, got {address}"
        )
        raise ValueError(
            f"Address must be between {address_start} and {address_end}, got {address}"
        )


def validate_wire_value(value: int, num_bits: int) -> None:
    _validate_plain_int("value", value)
    _validate_plain_int("num_bits", num_bits)
    if value < 0 or value > (2**num_bits - 1):
        logger.error(f"Value must be between 0 and {2**num_bits - 1}, got {value}")
        raise ValueError(f"Value must be between 0 and {2**num_bits - 1}, got {value}")


def validate_block_size(block_size: int, max_block_size: int) -> None:
    if block_size is None:
        return
    _validate_plain_int("block_size", block_size)
    _validate_plain_int("max_block_size", max_block_size)
    if block_size < 0:
        logger.error(f"Block size must be non-negative, got {block_size}")
        raise ValueError(f"Block size must be non-negative, got {block_size}")
    if max_block_size >= 0 and block_size > max_block_size:
        logger.error(f"Max block size is {max_block_size}, got {block_size}")
        raise ValueError(f"Max block size is {max_block_size}, got {block_size}")
