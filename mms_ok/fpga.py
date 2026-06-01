"""Compatibility facade for FPGA device classes.

The implementation is split across focused modules, while this module preserves
legacy imports such as ``from mms_ok.fpga import XEM7310`` and
``from mms_ok import fpga``.
"""

from __future__ import annotations

from .fpga_base import XEM
from .fpga_xem7310 import XEM7310
from .fpga_xem7360 import XEM7360

__all__ = ["XEM", "XEM7310", "XEM7360"]
