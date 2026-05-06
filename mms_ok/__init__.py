"""Public package interface for mms_ok.

The package keeps imports lightweight: FrontPanel setup is only attempted when
hardware-backed classes are actually accessed.
"""

try:
    from importlib.metadata import PackageNotFoundError, version as _metadata_version
except ImportError:  # pragma: no cover - Python 3.7 fallback
    from pkg_resources import DistributionNotFound as PackageNotFoundError
    from pkg_resources import get_distribution

    def _metadata_version(package_name: str) -> str:
        return get_distribution(package_name).version

from .ok_setup import copy_frontpanel_files

setup_frontpanel = copy_frontpanel_files

try:
    __version__ = _metadata_version("mms_ok")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "BIST",
    "XEM7310",
    "XEM7360",
    "__version__",
    "copy_frontpanel_files",
    "list_devices",
    "setup_frontpanel",
]

import sys
from loguru import logger

logger.remove()

logger.add(
    sys.stderr,
    format="[MMS OK] <green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
)


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
    if name == "list_devices":
        from .devices import list_devices

        return list_devices
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))


def __dir__():
    return sorted(__all__)
