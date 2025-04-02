from loguru import logger


def validate_address(address_start: int, address_end: int, address: int) -> None:
    if address < address_start or address > address_end:
        logger.error(
            f"Address must be between {address_start} and {address_end}, got {address}"
        )
        raise ValueError(
            f"Address must be between {address_start} and {address_end}, got {address}"
        )


def validate_wire_value(value: int, num_bits: int) -> None:
    if value < 0 or value > (2**num_bits - 1):
        logger.error(f"Value must be between 0 and {2**num_bits - 1}, got {value}")
        raise ValueError(f"Value must be between 0 and {2**num_bits - 1}, got {value}")


def validate_block_size(block_size: int, max_block_size: int) -> None:
    if block_size is None:
        return
    if block_size < 0 or block_size > max_block_size:
        logger.error(f"Max block size is {max_block_size}, got {block_size}")
        raise ValueError(f"Max block size is {max_block_size}, got {block_size}")
