import importlib
import os
import shutil
import sys

from loguru import logger

DEFAULT_FRONTPANEL_DIR = r"C:\Program Files\Opal Kelly\FrontPanelUSB"
DEFAULT_LIB_DIR = os.path.expanduser("~/mms_ok")
_ok_module = None


def _append_sys_path(path: str) -> None:
    if path not in sys.path:
        sys.path.append(path)


def copy_frontpanel_files(
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR, lib_dir: str = DEFAULT_LIB_DIR
):
    if os.name != "nt":
        logger.info("OS is not Windows!")
        return None

    if not os.path.exists(frontpanel_dir):
        logger.warning("FrontPanel SDK not found!")
        logger.warning(f"Default Directory: {frontpanel_dir}")
        return None

    os.makedirs(lib_dir, exist_ok=True)

    try:
        files = [
            os.path.join(frontpanel_dir, "API/Python/x64/ok.py"),
            os.path.join(frontpanel_dir, "API/Python/x64/_ok.pyd"),
            os.path.join(frontpanel_dir, "API/lib/x64/okFrontPanel.dll"),
        ]

        for file in files:
            shutil.copy(src=file, dst=lib_dir)

        _append_sys_path(lib_dir)
        return lib_dir
    except FileNotFoundError:
        logger.warning("FrontPanel SDK files not found!")
        logger.warning(f"Default Directory: {frontpanel_dir}")
        return None


def import_ok():
    try:
        return importlib.import_module("ok")
    except ImportError:
        copied_dir = copy_frontpanel_files()
        if copied_dir:
            _append_sys_path(copied_dir)
            try:
                return importlib.import_module("ok")
            except ImportError:
                pass

    logger.critical("Please manually setup FrontPanel SDK!")
    raise ImportError("Import ok failed")


def get_ok():
    global _ok_module

    if _ok_module is None:
        _ok_module = import_ok()

    return _ok_module


def get_frontpanel_version(ok_module=None) -> str:
    ok = ok_module or get_ok()

    for owner in (ok, getattr(ok, "okCFrontPanel", None)):
        if owner is None:
            continue

        get_version_string = getattr(owner, "GetAPIVersionString", None)
        if get_version_string is not None:
            try:
                version = get_version_string()
                return version.decode() if isinstance(version, bytes) else str(version)
            except Exception:
                pass

    try:
        return "{}.{}.{}".format(
            ok.GetAPIVersionMajor(),
            ok.GetAPIVersionMinor(),
            ok.GetAPIVersionMicro(),
        )
    except Exception:
        return "unknown"
