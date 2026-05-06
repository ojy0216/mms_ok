import importlib
import os
import shutil
import sys
from struct import calcsize

from loguru import logger

from .diagnostics import log_critical

DEFAULT_FRONTPANEL_DIR = r"C:\Program Files\Opal Kelly\FrontPanelUSB"
DEFAULT_LIB_DIR = os.path.expanduser("~/mms_ok")
_ok_module = None
FRONTPANEL_FILENAMES = ("ok.py", "_ok.pyd", "okFrontPanel.dll")


def _append_sys_path(path: str) -> None:
    if path not in sys.path:
        sys.path.append(path)


def _frontpanel_files_exist(lib_dir: str = DEFAULT_LIB_DIR) -> bool:
    return all(
        os.path.isfile(os.path.join(lib_dir, name)) for name in FRONTPANEL_FILENAMES
    )


def _frontpanel_cache_is_partial(lib_dir: str = DEFAULT_LIB_DIR) -> bool:
    existing_files = [
        os.path.isfile(os.path.join(lib_dir, name)) for name in FRONTPANEL_FILENAMES
    ]
    return any(existing_files) and not all(existing_files)


def resolve_path(path: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def frontpanel_file_sources(frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR):
    frontpanel_dir = resolve_path(frontpanel_dir)
    return {
        "ok.py": os.path.join(frontpanel_dir, "API/Python/x64/ok.py"),
        "_ok.pyd": os.path.join(frontpanel_dir, "API/Python/x64/_ok.pyd"),
        "okFrontPanel.dll": os.path.join(
            frontpanel_dir, "API/lib/x64/okFrontPanel.dll"
        ),
    }


def frontpanel_cache_status(lib_dir: str = DEFAULT_LIB_DIR):
    lib_dir = resolve_path(lib_dir)
    files = {
        name: {
            "path": os.path.join(lib_dir, name),
            "exists": os.path.isfile(os.path.join(lib_dir, name)),
        }
        for name in FRONTPANEL_FILENAMES
    }
    existing_count = sum(1 for info in files.values() if info["exists"])
    return {
        "path": lib_dir,
        "files": files,
        "complete": existing_count == len(FRONTPANEL_FILENAMES),
        "partial": 0 < existing_count < len(FRONTPANEL_FILENAMES),
        "missing": existing_count == 0,
    }


def python_bitness() -> int:
    return calcsize("P") * 8


def probe_frontpanel_import(lib_dir: str = DEFAULT_LIB_DIR):
    """Probe ok/_ok imports without copying or refreshing FrontPanel files."""
    lib_dir = resolve_path(lib_dir)
    result = {
        "ok_module": None,
        "ok_imported": False,
        "_ok_imported": False,
        "ok_error": None,
        "_ok_error": None,
        "used_cache_path": False,
    }

    try:
        result["ok_module"] = importlib.import_module("ok")
        result["ok_imported"] = True
    except Exception as exc:
        result["ok_error"] = "{}: {}".format(type(exc).__name__, exc)

    if not result["ok_imported"] and _frontpanel_files_exist(lib_dir):
        _append_sys_path(lib_dir)
        result["used_cache_path"] = True
        try:
            result["ok_module"] = importlib.import_module("ok")
            result["ok_imported"] = True
            result["ok_error"] = None
        except Exception as exc:
            result["ok_error"] = "{}: {}".format(type(exc).__name__, exc)

    if os.path.isfile(os.path.join(lib_dir, "_ok.pyd")):
        _append_sys_path(lib_dir)

    try:
        importlib.import_module("_ok")
        result["_ok_imported"] = True
    except Exception as exc:
        result["_ok_error"] = "{}: {}".format(type(exc).__name__, exc)

    return result


def copy_frontpanel_files(
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
    lib_dir: str = DEFAULT_LIB_DIR,
    overwrite: bool = False,
    raise_errors: bool = False,
):
    if os.name != "nt":
        logger.info("OS is not Windows!")
        return None

    frontpanel_dir = resolve_path(frontpanel_dir)
    lib_dir = resolve_path(lib_dir)

    if not os.path.exists(frontpanel_dir):
        logger.warning("FrontPanel SDK not found!")
        logger.warning(f"Default Directory: {frontpanel_dir}")
        return None

    os.makedirs(lib_dir, exist_ok=True)

    try:
        refresh_cache = overwrite or _frontpanel_cache_is_partial(lib_dir)
        files = frontpanel_file_sources(frontpanel_dir)

        for filename, source in files.items():
            destination = os.path.join(lib_dir, filename)
            if os.path.exists(destination) and not refresh_cache:
                logger.info(f"Using existing FrontPanel file: {destination}")
                continue
            shutil.copy(src=source, dst=destination)

        _append_sys_path(lib_dir)
        return lib_dir
    except FileNotFoundError:
        if raise_errors:
            raise
        logger.warning("FrontPanel SDK files not found!")
        logger.warning(f"Default Directory: {frontpanel_dir}")
        return None
    except PermissionError as exc:
        if raise_errors:
            raise
        logger.warning(f"FrontPanel SDK file copy failed: {exc}")
        logger.warning(
            "Close other Python/Jupyter processes using FrontPanel, or restart their kernels."
        )
        return None


def reset_frontpanel_cache(
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
    lib_dir: str = DEFAULT_LIB_DIR,
):
    return copy_frontpanel_files(
        frontpanel_dir=frontpanel_dir,
        lib_dir=lib_dir,
        overwrite=True,
        raise_errors=True,
    )


def import_ok():
    try:
        return importlib.import_module("ok")
    except ImportError:
        pass

    if _frontpanel_files_exist():
        _append_sys_path(DEFAULT_LIB_DIR)
        try:
            return importlib.import_module("ok")
        except ImportError:
            logger.warning(
                "Existing FrontPanel files could not be imported; refreshing cache."
            )

    copied_dir = copy_frontpanel_files(overwrite=True)
    if copied_dir:
        _append_sys_path(copied_dir)
        try:
            return importlib.import_module("ok")
        except ImportError:
            pass

    log_critical("Please manually setup FrontPanel SDK!")
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
