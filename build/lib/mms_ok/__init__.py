"""Public package interface for mms_ok.

The package keeps imports lightweight: FrontPanel setup is only attempted when
hardware-backed classes are actually accessed.
"""

from pkg_resources import DistributionNotFound, get_distribution

from .ok_setup import copy_frontpanel_files

setup_frontpanel = copy_frontpanel_files

try:
    __version__ = get_distribution("mms_ok").version
except DistributionNotFound:
    __version__ = "0+unknown"

__all__ = [
    "BIST",
    "XEM7310",
    "XEM7360",
    "__version__",
    "copy_frontpanel_files",
    "setup_frontpanel",
]


def __getattr__(name):
    if name == "BIST":
        from .bist import BIST

        return BIST
    if name in {"XEM7310", "XEM7360"}:
        from .fpga import XEM7310, XEM7360

        return {"XEM7310": XEM7310, "XEM7360": XEM7360}[name]
    if name == "copy_frontpanel_files":
        return copy_frontpanel_files
    if name == "setup_frontpanel":
        return setup_frontpanel
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))


def __dir__():
    return sorted(__all__)
