"""Test harness for package-level Windows runtime enforcement.

Legacy unit tests exercise Windows runtime behavior from a Linux CI host. Load the
local package once under a short-lived ``os.name == 'nt'`` simulation without
routing through editable-install finders, which may use pathlib while ``os.name``
is patched.
"""

import importlib.util
import os
import sys

from loguru import logger as _logger  # noqa: F401  # preload before simulation


_ORIGINAL_OS_NAME = os.name
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_PACKAGE_DIR = os.path.join(_PROJECT_ROOT, "mms_ok")


def _load_local_package_under_windows_simulation() -> None:
    if "mms_ok" in sys.modules:
        return

    spec = importlib.util.spec_from_file_location(
        "mms_ok",
        os.path.join(_PACKAGE_DIR, "__init__.py"),
        submodule_search_locations=[_PACKAGE_DIR],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load local mms_ok package for tests")

    module = importlib.util.module_from_spec(spec)
    sys.modules["mms_ok"] = module

    os.name = "nt"
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop("mms_ok", None)
        raise
    finally:
        os.name = _ORIGINAL_OS_NAME


if _ORIGINAL_OS_NAME != "nt":
    _load_local_package_under_windows_simulation()
