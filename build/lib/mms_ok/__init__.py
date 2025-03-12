from loog import log

from .ok_setup import copy_frontpanel_files

copy_frontpanel_files()

try:
    import ok
except ImportError:
    log("Please manually setup FrontPanel SDK!", level="critical")
    raise ImportError("Import ok failed")

from .fpga import XEM7310, XEM7360
