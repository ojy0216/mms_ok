import importlib
import os
import shutil
import sys
from struct import calcsize
from typing import Optional

from loguru import logger

from .diagnostics import log_critical

DEFAULT_FRONTPANEL_DIR = r"C:\Program Files\Opal Kelly\FrontPanelUSB"
DEFAULT_LIB_DIR = os.path.expanduser("~/mms_ok")
_ok_module = None
FRONTPANEL_FILENAMES = ("ok.py", "_ok.pyd", "okFrontPanel.dll")


def _append_sys_path(path: str) -> None:
    if path not in sys.path:
        sys.path.append(path)


def _prepend_sys_path(path: str) -> None:
    path = resolve_path(path)
    sys.path[:] = [entry for entry in sys.path if resolve_path(entry) != path]
    sys.path.insert(0, path)


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


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(resolve_path(left)) == os.path.normcase(
        resolve_path(right)
    )


def _trusted_ok_paths(
    lib_dir: str = DEFAULT_LIB_DIR,
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
):
    paths = [
        os.path.join(resolve_path(lib_dir), "ok.py"),
        resolve_path(frontpanel_file_sources(frontpanel_dir)["ok.py"]),
    ]
    trusted = []
    for path in paths:
        if not any(_same_path(path, existing) for existing in trusted):
            trusted.append(path)
    return tuple(trusted)


def _trusted_ok_dirs(
    lib_dir: str = DEFAULT_LIB_DIR,
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
):
    return tuple(
        os.path.dirname(path) for path in _trusted_ok_paths(lib_dir, frontpanel_dir)
    )


def _has_version_accessor(owner) -> bool:
    if owner is None:
        return False

    get_version_string = getattr(owner, "GetAPIVersionString", None)
    if callable(get_version_string):
        return True

    return all(
        callable(getattr(owner, name, None))
        for name in (
            "GetAPIVersionMajor",
            "GetAPIVersionMinor",
            "GetAPIVersionMicro",
        )
    )


def _frontpanel_symbols_error(ok_module) -> Optional[str]:
    frontpanel_class = getattr(ok_module, "okCFrontPanel", None)
    if frontpanel_class is None:
        return "ok module is missing okCFrontPanel"

    if not (
        _has_version_accessor(ok_module) or _has_version_accessor(frontpanel_class)
    ):
        return "ok module is missing FrontPanel API version accessors"

    return None


def _ok_module_validation_error(
    ok_module,
    lib_dir: str = DEFAULT_LIB_DIR,
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
) -> Optional[str]:
    module_file = getattr(ok_module, "__file__", None)
    trusted_paths = _trusted_ok_paths(lib_dir, frontpanel_dir)
    if module_file is None:
        return "ok module has no __file__; expected one of: {}".format(
            ", ".join(trusted_paths)
        )

    if not any(_same_path(module_file, path) for path in trusted_paths):
        return "untrusted ok module path: {}; expected one of: {}".format(
            resolve_path(module_file), ", ".join(trusted_paths)
        )

    return _frontpanel_symbols_error(ok_module)


def _format_exception(exc: Exception) -> str:
    return "{}: {}".format(type(exc).__name__, exc)


def _drop_untrusted_loaded_ok(
    lib_dir: str = DEFAULT_LIB_DIR,
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
) -> Optional[str]:
    loaded_ok = sys.modules.get("ok")
    if loaded_ok is None:
        return None

    error = _ok_module_validation_error(loaded_ok, lib_dir, frontpanel_dir)
    if error is None:
        return None

    sys.modules.pop("ok", None)
    return error


def _import_ok_from_dir(
    directory: str,
    lib_dir: str = DEFAULT_LIB_DIR,
    frontpanel_dir: str = DEFAULT_FRONTPANEL_DIR,
):
    _prepend_sys_path(directory)
    _drop_untrusted_loaded_ok(lib_dir, frontpanel_dir)
    ok_module = importlib.import_module("ok")
    error = _ok_module_validation_error(ok_module, lib_dir, frontpanel_dir)
    if error is not None:
        sys.modules.pop("ok", None)
        raise ImportError(error)
    return ok_module


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

    loaded_ok = sys.modules.get("ok")
    if loaded_ok is not None:
        error = _ok_module_validation_error(loaded_ok, lib_dir)
        if error is None:
            result["ok_module"] = loaded_ok
            result["ok_imported"] = True
        else:
            sys.modules.pop("ok", None)
            result["ok_error"] = error

    if not result["ok_imported"] and _frontpanel_files_exist(lib_dir):
        _prepend_sys_path(lib_dir)
        result["used_cache_path"] = True
        try:
            result["ok_module"] = _import_ok_from_dir(lib_dir, lib_dir=lib_dir)
            result["ok_imported"] = True
            result["ok_error"] = None
        except Exception as exc:
            if result["ok_error"] is None:
                result["ok_error"] = _format_exception(exc)

    if not result["ok_imported"]:
        for directory in _trusted_ok_dirs(lib_dir):
            ok_path = os.path.join(directory, "ok.py")
            if _same_path(directory, lib_dir) or not os.path.isfile(ok_path):
                continue
            try:
                result["ok_module"] = _import_ok_from_dir(directory, lib_dir=lib_dir)
                result["ok_imported"] = True
                result["ok_error"] = None
                break
            except Exception as exc:
                if result["ok_error"] is None:
                    result["ok_error"] = _format_exception(exc)

    if not result["ok_imported"] and result["ok_error"] is None:
        result["ok_error"] = "trusted FrontPanel ok.py was not found"

    if os.path.isfile(os.path.join(lib_dir, "_ok.pyd")):
        _prepend_sys_path(lib_dir)

    try:
        importlib.import_module("_ok")
        result["_ok_imported"] = True
    except Exception as exc:
        result["_ok_error"] = _format_exception(exc)

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
    loaded_ok = sys.modules.get("ok")
    if loaded_ok is not None:
        error = _ok_module_validation_error(loaded_ok, DEFAULT_LIB_DIR)
        if error is None:
            return loaded_ok
        sys.modules.pop("ok", None)

    if _frontpanel_files_exist(DEFAULT_LIB_DIR):
        _prepend_sys_path(DEFAULT_LIB_DIR)
        try:
            return _import_ok_from_dir(DEFAULT_LIB_DIR, lib_dir=DEFAULT_LIB_DIR)
        except Exception:
            logger.warning(
                "Existing FrontPanel files could not be imported; refreshing cache."
            )

    copied_dir = copy_frontpanel_files(lib_dir=DEFAULT_LIB_DIR, overwrite=True)
    if copied_dir:
        _prepend_sys_path(copied_dir)
        try:
            return _import_ok_from_dir(copied_dir, lib_dir=DEFAULT_LIB_DIR)
        except Exception:
            pass

    for directory in _trusted_ok_dirs(DEFAULT_LIB_DIR):
        ok_path = os.path.join(directory, "ok.py")
        if _same_path(directory, DEFAULT_LIB_DIR) or not os.path.isfile(ok_path):
            continue
        try:
            return _import_ok_from_dir(directory, lib_dir=DEFAULT_LIB_DIR)
        except Exception:
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
