"""Lazy, source-checked loading of the vendor FrontPanel binding API."""

import importlib
import importlib.util
import os
import shutil
import sys
from contextlib import contextmanager
from struct import calcsize
from typing import Optional

try:
    from importlib import metadata
except ImportError:  # Python 3.7 can still use the FrontPanel 5 SDK files.
    metadata = None

from loguru import logger

DEFAULT_FRONTPANEL_DIR = r"C:\Program Files\Opal Kelly\FrontPanelUSB"
DEFAULT_LIB_DIR = os.path.expanduser("~/mms_ok")
FRONTPANEL_DIR_ENV = "MMS_OK_FRONTPANEL_DIR"
WINDOWS_FRONTPANEL_FILENAMES = ("ok.py", "_ok.pyd", "okFrontPanel.dll")
MACOS_FRONTPANEL_FILENAMES = ("ok.py", "_ok.so", "libokFrontPanel.2.dylib")
_ok_module = None


def _is_macos():
    return os.name != "nt" and sys.platform == "darwin"


def frontpanel_filenames():
    return MACOS_FRONTPANEL_FILENAMES if _is_macos() else WINDOWS_FRONTPANEL_FILENAMES


FRONTPANEL_FILENAMES = frontpanel_filenames()


def resolve_path(path: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def selected_frontpanel_dir(frontpanel_dir=None):
    directory = frontpanel_dir or os.environ.get(FRONTPANEL_DIR_ENV)
    if not directory and not _is_macos():
        directory = DEFAULT_FRONTPANEL_DIR
    return resolve_path(directory) if directory else None


def frontpanel_file_sources(frontpanel_dir: Optional[str] = None):
    directory = selected_frontpanel_dir(frontpanel_dir)
    if not directory:
        raise FileNotFoundError(
            "Specify --frontpanel-dir or MMS_OK_FRONTPANEL_DIR to copy SDK files. "
            "On macOS the recommended setup is the official ok wheel from API/Python."
        )
    if _is_macos():
        # Accept either the SDK root or its API/Python directory.
        python_dir = (
            directory if os.path.isfile(os.path.join(directory, "ok.py"))
            else os.path.join(directory, "API", "Python")
        )
        dylib_dirs = (python_dir, os.path.dirname(python_dir))
        dylib = next(
            (
                os.path.join(d, "libokFrontPanel.2.dylib") for d in dylib_dirs
                if os.path.isfile(os.path.join(d, "libokFrontPanel.2.dylib"))
            ),
            os.path.join(os.path.dirname(python_dir), "libokFrontPanel.2.dylib"),
        )
        return {
            "ok.py": os.path.join(python_dir, "ok.py"),
            "_ok.so": os.path.join(python_dir, "_ok.so"),
            "libokFrontPanel.2.dylib": dylib,
        }
    return {
        "ok.py": os.path.join(directory, "API/Python/x64/ok.py"),
        "_ok.pyd": os.path.join(directory, "API/Python/x64/_ok.pyd"),
        "okFrontPanel.dll": os.path.join(directory, "API/lib/x64/okFrontPanel.dll"),
    }


def _same_path(left, right):
    return os.path.normcase(os.path.realpath(resolve_path(left))) == os.path.normcase(
        os.path.realpath(resolve_path(right))
    )


def frontpanel_cache_status(lib_dir=None):
    lib_dir = resolve_path(lib_dir or DEFAULT_LIB_DIR)
    files = {
        name: {
            "path": os.path.join(lib_dir, name),
            "exists": os.path.isfile(os.path.join(lib_dir, name)),
        }
        for name in frontpanel_filenames()
    }
    count = sum(info["exists"] for info in files.values())
    return {
        "path": lib_dir, "files": files, "complete": count == len(files),
        "partial": 0 < count < len(files), "missing": count == 0,
    }


def _frontpanel_files_exist(lib_dir=None):
    return frontpanel_cache_status(lib_dir)["complete"]


def _frontpanel_cache_is_partial(lib_dir=None):
    return frontpanel_cache_status(lib_dir)["partial"]


def _has_version_accessor(owner):
    return owner is not None and (
        callable(getattr(owner, "GetAPIVersionString", None)) or all(
            callable(getattr(owner, name, None)) for name in
            ("GetAPIVersionMajor", "GetAPIVersionMinor", "GetAPIVersionMicro")
        )
    )


def _frontpanel_symbols_error(module):
    if not hasattr(module, "okCFrontPanel"):
        return "ok module is missing okCFrontPanel"
    if not (_has_version_accessor(module) or _has_version_accessor(module.okCFrontPanel)):
        return "ok module is missing FrontPanel API version accessors"
    return None


def _wheel_candidate():
    """Locate the installed distribution's recorded files, never a sys.path hit."""
    if metadata is None:
        return None
    try:
        dist = metadata.distribution("ok")
    except metadata.PackageNotFoundError:
        return None
    files = {
        str(f).replace("\\", "/"): str(dist.locate_file(f))
        for f in (dist.files or ())
    }
    ok_path = files.get("ok/__init__.py")
    binding_path = files.get("ok/ok.py")
    natives = [
        path for name, path in files.items()
        if name.startswith("ok/_ok") and name.endswith(".so")
    ]
    if not ok_path or not binding_path or len(natives) != 1:
        return None
    return {
        "kind": "wheel", "ok_path": ok_path, "binding_path": binding_path,
        "native_path": natives[0],
        "directory": os.path.dirname(os.path.dirname(ok_path)),
        "files": [ok_path, binding_path, natives[0]], "version": dist.version,
    }


def _file_candidate(kind, files):
    return {
        "kind": kind, "ok_path": files["ok.py"],
        "native_path": files["_ok.so" if _is_macos() else "_ok.pyd"],
        "directory": os.path.dirname(files["ok.py"]), "files": list(files.values()),
        "dll_dir": os.path.dirname(files.get("okFrontPanel.dll", files["ok.py"])),
    }


def _candidates(lib_dir, frontpanel_dir):
    cache = _file_candidate(
        "cache", {n: os.path.join(lib_dir, n) for n in frontpanel_filenames()}
    )
    sdk_dir = selected_frontpanel_dir(frontpanel_dir)
    sdk = _file_candidate("sdk", frontpanel_file_sources(sdk_dir)) if sdk_dir else None
    if _is_macos():
        return [c for c in (sdk, _wheel_candidate(), cache) if c is not None]
    return [c for c in (cache, sdk) if c is not None]


def _clear_frontpanel_modules():
    global _ok_module
    _ok_module = None
    for name in list(sys.modules):
        if name in ("ok", "_ok") or name.startswith("ok."):
            sys.modules.pop(name, None)


def _module_path_error(module, expected, name):
    path = getattr(module, "__file__", None)
    if not path or not _same_path(path, expected):
        return "untrusted {} module path: {}; expected {}".format(name, path, expected)
    return None


def _candidate_module_error(module, candidate):
    error = _module_path_error(
        module, candidate["ok_path"], "ok"
    ) or _frontpanel_symbols_error(module)
    if error:
        return error
    if candidate["kind"] == "wheel":
        binding = sys.modules.get("ok.ok")
        if binding is None:
            return "official ok wheel is missing its ok.ok binding module"
        error = _module_path_error(binding, candidate["binding_path"], "ok.ok")
        if error:
            return error
    for name in ("_ok", "ok._ok"):
        native = sys.modules.get(name)
        if native is not None:
            error = _module_path_error(native, candidate["native_path"], name)
            if error:
                return error
    return None


@contextmanager
def _scoped_frontpanel_import_path(directory, dll_dir=None):
    original_path = list(sys.path)
    cookie = None
    try:
        sys.path.insert(0, resolve_path(directory))
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if (
            os.name == "nt" and add_dll_directory is not None
            and dll_dir and os.path.isdir(dll_dir)
        ):
            cookie = add_dll_directory(dll_dir)
        yield
    finally:
        if cookie is not None:
            cookie.close()
        sys.path[:] = original_path


def _python_environment_error(candidate):
    # The macOS SDK and wheel use the CPython 3.11 stable ABI.
    version = candidate.get("version", "")
    if _is_macos() or version.startswith("6.1."):
        if sys.version_info < (3, 11):
            return "FrontPanel 6.1 requires Python 3.11 or newer (running {})".format(
                sys.version.split()[0]
            )
    return None


def _load_candidate(candidate):
    environment_error = _python_environment_error(candidate)
    if environment_error:
        raise ImportError(environment_error)
    missing = [f for f in candidate["files"] if not os.path.isfile(f)]
    if missing:
        raise ImportError("Missing FrontPanel file(s): " + ", ".join(missing))
    loaded = sys.modules.get("ok")
    if loaded is not None and _candidate_module_error(loaded, candidate) is None:
        return loaded
    _clear_frontpanel_modules()
    try:
        # Loading the exact file prevents an unrelated ok.py or package from
        # winning module resolution. Only the SDK's native import needs sys.path.
        is_package = candidate["kind"] == "wheel"
        spec = importlib.util.spec_from_file_location(
            "ok", candidate["ok_path"],
            submodule_search_locations=(
                [os.path.dirname(candidate["ok_path"])] if is_package else None
            ),
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["ok"] = module
        with _scoped_frontpanel_import_path(candidate["directory"], candidate.get("dll_dir")):
            spec.loader.exec_module(module)
        error = _candidate_module_error(module, candidate)
        if error:
            raise ImportError(error)
        version = get_frontpanel_version(module)
        if sys.version_info < (3, 11) and version.startswith("6.1."):
            raise ImportError("FrontPanel 6.1 requires Python 3.11 or newer")
        return module
    except BaseException:
        _clear_frontpanel_modules()
        raise


def python_bitness() -> int:
    return calcsize("P") * 8


def _format_exception(exc):
    return "{}: {}".format(type(exc).__name__, exc)


def probe_frontpanel_import(lib_dir=None, frontpanel_dir=None):
    """Inspect SDK/wheel/cache imports without copying or refreshing files."""
    lib_dir = resolve_path(lib_dir or DEFAULT_LIB_DIR)
    result = {
        "ok_module": None, "ok_imported": False, "_ok_imported": False,
        "ok_error": None, "_ok_error": None, "used_cache_path": False,
        "source": None, "ok_path": None, "native_path": None, "attempts": [],
    }
    candidates = _candidates(lib_dir, frontpanel_dir)
    loaded = sys.modules.get("ok")
    if loaded is not None and not any(
        _candidate_module_error(loaded, c) is None for c in candidates
    ):
        result["attempts"].append(
            "untrusted ok module path: {}".format(getattr(loaded, "__file__", None))
        )
        _clear_frontpanel_modules()
    for candidate in candidates:
        try:
            module = _load_candidate(candidate)
        except Exception as exc:
            result["attempts"].append("{}: {}".format(candidate["kind"], _format_exception(exc)))
            continue
        result.update(
            ok_module=module, ok_imported=True, source=candidate["kind"],
            used_cache_path=candidate["kind"] == "cache", ok_path=module.__file__,
        )
        name = "ok._ok" if candidate["kind"] == "wheel" else "_ok"
        try:
            with _scoped_frontpanel_import_path(candidate["directory"], candidate.get("dll_dir")):
                native = importlib.import_module(name)
            error = _module_path_error(native, candidate["native_path"], name)
            if error:
                raise ImportError(error)
            result.update(_ok_imported=True, native_path=native.__file__)
        except Exception as exc:
            result["_ok_error"] = _format_exception(exc)
        break
    if not result["ok_imported"]:
        result["ok_error"] = "; ".join(result["attempts"]) or "trusted FrontPanel ok module was not found"
        result["_ok_error"] = result["ok_error"]
    return result


def copy_frontpanel_files(frontpanel_dir=None, lib_dir=None, overwrite=False, raise_errors=False):
    if os.name != "nt" and not _is_macos():
        logger.info("FrontPanel setup supports Windows and macOS")
        return None
    lib_dir = resolve_path(lib_dir or DEFAULT_LIB_DIR)
    try:
        files = frontpanel_file_sources(frontpanel_dir)
        # Check every source before changing the cache, including the dylib.
        for source in files.values():
            if not os.path.isfile(source):
                raise FileNotFoundError(source)
        os.makedirs(lib_dir, exist_ok=True)
        refresh = overwrite or _frontpanel_cache_is_partial(lib_dir)
        for filename, source in files.items():
            destination = os.path.join(lib_dir, filename)
            if os.path.isfile(destination) and (not refresh or _same_path(source, destination)):
                continue
            shutil.copy(source, destination)
        return lib_dir
    except (FileNotFoundError, PermissionError) as exc:
        if raise_errors:
            raise
        logger.warning("FrontPanel SDK file copy failed: {}", exc)
        return None


def reset_frontpanel_cache(frontpanel_dir=None, lib_dir=None):
    return copy_frontpanel_files(frontpanel_dir, lib_dir, overwrite=True, raise_errors=True)


def import_ok(frontpanel_dir=None, lib_dir=None):
    lib_dir = resolve_path(lib_dir or DEFAULT_LIB_DIR)
    # Windows keeps its historical automatic SDK-to-cache installation behavior.
    if not _is_macos() and not _frontpanel_files_exist(lib_dir):
        copy_frontpanel_files(frontpanel_dir=frontpanel_dir, lib_dir=lib_dir, overwrite=True)
    probe = probe_frontpanel_import(lib_dir, frontpanel_dir)
    if not probe["ok_imported"] and not _is_macos():
        copied = copy_frontpanel_files(frontpanel_dir=frontpanel_dir, lib_dir=lib_dir, overwrite=True)
        if copied:
            probe = probe_frontpanel_import(lib_dir, frontpanel_dir)
    if probe["ok_imported"]:
        return probe["ok_module"]
    raise ImportError(
        "Import ok failed: {}. Use `mms_ok doctor` for setup details.".format(
            probe["ok_error"]
        )
    )


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
        get_string = getattr(owner, "GetAPIVersionString", None)
        if callable(get_string):
            try:
                version = get_string()
                return version.decode() if isinstance(version, bytes) else str(version)
            except Exception:
                pass
        try:
            return "{}.{}.{}".format(
                owner.GetAPIVersionMajor(), owner.GetAPIVersionMinor(),
                owner.GetAPIVersionMicro(),
            )
        except Exception:
            pass
    return "unknown"
