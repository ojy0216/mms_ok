"""Compatibility facade for FPGA device classes.

The implementation is split across focused modules, while this module preserves
legacy imports such as ``from mms_ok.fpga import XEM7310`` and
``from mms_ok import fpga``.
"""

from __future__ import annotations

from .fpga_base import ProductIDMismatchError, XEM
from .fpga_factory import FPGASelectionError, XEM as autodetect_xem
from .fpga_generic import UnverifiedXEM
from .fpga_xem7310 import XEM7310
from .fpga_xem7360 import XEM7360

XEMBase = XEM

__all__ = [
    "FPGASelectionError",
    "ProductIDMismatchError",
    "UnverifiedXEM",
    "XEM",
    "XEMBase",
    "autodetect_xem",
    "XEM7310",
    "XEM7360",
]
