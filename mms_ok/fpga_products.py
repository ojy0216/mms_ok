"""Private FrontPanel product-id helpers for supported board families."""

from __future__ import annotations

from typing import Set

from .ok_setup import get_ok

XEM7310_PRODUCT_ID_NAMES = ("brdXEM7310A75", "brdXEM7310A200")
XEM7360_PRODUCT_ID_NAMES = ("brdXEM7360K160T",)
VERIFIED_PRODUCT_ID_NAMES = XEM7310_PRODUCT_ID_NAMES + XEM7360_PRODUCT_ID_NAMES


def _product_ids(names, ok_module=None) -> Set[int]:
    frontpanel = (ok_module or get_ok()).okCFrontPanel
    missing = [name for name in names if not hasattr(frontpanel, name)]
    if missing:
        raise AttributeError(
            "FrontPanel SDK is missing required product-id constants: {}".format(
                ", ".join(missing)
            )
        )
    return {int(getattr(frontpanel, name)) for name in names}


def xem7310_product_ids(ok_module=None) -> Set[int]:
    """Return FrontPanel product IDs for verified XEM7310 variants."""
    return _product_ids(XEM7310_PRODUCT_ID_NAMES, ok_module)


def xem7360_product_ids(ok_module=None) -> Set[int]:
    """Return FrontPanel product IDs for verified XEM7360 variants."""
    return _product_ids(XEM7360_PRODUCT_ID_NAMES, ok_module)


def verified_product_ids(ok_module=None) -> Set[int]:
    """Return all product IDs with hardware-verified board classes."""
    return _product_ids(VERIFIED_PRODUCT_ID_NAMES, ok_module)
