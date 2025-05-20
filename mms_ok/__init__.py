from loguru import logger

from .ok_setup import copy_frontpanel_files

copy_frontpanel_files()

try:
    import ok
except ImportError:
    logger.critical("Please manually setup FrontPanel SDK!")
    raise ImportError("Import ok failed")

from .fpga import XEM7310, XEM7360
from .bist import BIST
