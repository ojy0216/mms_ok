from __future__ import annotations

import importlib
import os
import sys
import types

import pytest

from mms_ok import ok_setup


VALID_OK = """
class okCFrontPanel:
    @staticmethod
    def GetAPIVersionString():
        return "1.2.3"
"""


MISSING_SYMBOLS_OK = """
class NotFrontPanel:
    pass
"""


def _write_frontpanel_cache(cache_dir, ok_source=VALID_OK):
    cache_dir.mkdir()
    (cache_dir / "ok.py").write_text(ok_source, encoding="utf-8")
    (cache_dir / "_ok.pyd").write_text("", encoding="utf-8")
    (cache_dir / "okFrontPanel.dll").write_text("", encoding="utf-8")
    return cache_dir


def _write_frontpanel_sdk(sdk_dir, ok_source=VALID_OK):
    python_dir = sdk_dir / "API" / "Python" / "x64"
    dll_dir = sdk_dir / "API" / "lib" / "x64"
    python_dir.mkdir(parents=True)
    dll_dir.mkdir(parents=True)
    (python_dir / "ok.py").write_text(ok_source, encoding="utf-8")
    (python_dir / "_ok.pyd").write_text("", encoding="utf-8")
    (dll_dir / "okFrontPanel.dll").write_text("", encoding="utf-8")
    return sdk_dir


@pytest.fixture(autouse=True)
def isolate_ok_import_state(monkeypatch, tmp_path):
    old_path = list(sys.path)
    sentinel = object()
    old_modules = {
        name: sys.modules.get(name, sentinel)
        for name in ("ok", "_ok")
    }
    monkeypatch.setattr(
        ok_setup,
        "DEFAULT_FRONTPANEL_DIR",
        str(tmp_path / "missing-default-sdk"),
    )

    sys.modules.pop("ok", None)
    sys.modules.pop("_ok", None)

    yield

    sys.path[:] = old_path
    for name, module in old_modules.items():
        if module is sentinel:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def test_import_ok_ignores_untrusted_ok_earlier_on_sys_path(monkeypatch, tmp_path):
    cache_dir = _write_frontpanel_cache(tmp_path / "cache")
    malicious_dir = tmp_path / "malicious"
    malicious_dir.mkdir()
    (malicious_dir / "ok.py").write_text(
        """
class okCFrontPanel:
    @staticmethod
    def GetAPIVersionString():
        return "9.9.9"
""",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(malicious_dir))
    monkeypatch.setattr(ok_setup, "DEFAULT_LIB_DIR", str(cache_dir))
    original_path = list(sys.path)

    ok = ok_setup.import_ok()

    assert os.path.samefile(ok.__file__, cache_dir / "ok.py")
    assert "malicious" not in ok.__file__
    assert sys.path == original_path
    assert str(malicious_dir) in sys.path


def test_import_ok_accepts_trusted_cache_with_frontpanel_symbols(monkeypatch, tmp_path):
    cache_dir = _write_frontpanel_cache(tmp_path / "cache")
    monkeypatch.setattr(ok_setup, "DEFAULT_LIB_DIR", str(cache_dir))
    original_path = list(sys.path)

    ok = ok_setup.import_ok()

    assert os.path.samefile(ok.__file__, cache_dir / "ok.py")
    assert hasattr(ok, "okCFrontPanel")
    assert ok.okCFrontPanel.GetAPIVersionString() == "1.2.3"
    assert sys.path == original_path


def test_import_ok_rejects_trusted_cache_missing_frontpanel_symbols(
    monkeypatch, tmp_path
):
    cache_dir = _write_frontpanel_cache(
        tmp_path / "cache",
        ok_source=MISSING_SYMBOLS_OK,
    )
    monkeypatch.setattr(ok_setup, "DEFAULT_LIB_DIR", str(cache_dir))
    monkeypatch.setattr(ok_setup, "copy_frontpanel_files", lambda **_kwargs: None)

    with pytest.raises(ImportError, match="Import ok failed"):
        ok_setup.import_ok()

    assert "ok" not in sys.modules


def test_import_ok_drops_untrusted_loaded_native_module(monkeypatch, tmp_path):
    cache_dir = _write_frontpanel_cache(tmp_path / "cache")
    malicious_dir = tmp_path / "malicious"
    malicious_dir.mkdir()
    native_module = types.ModuleType("_ok")
    native_module.__file__ = str(malicious_dir / "_ok.pyd")
    sys.modules["_ok"] = native_module
    monkeypatch.setattr(ok_setup, "DEFAULT_LIB_DIR", str(cache_dir))
    original_path = list(sys.path)

    ok = ok_setup.import_ok()

    assert os.path.samefile(ok.__file__, cache_dir / "ok.py")
    assert sys.modules.get("_ok") is not native_module
    assert sys.path == original_path


def test_probe_frontpanel_import_rejects_untrusted_loaded_ok(tmp_path):
    malicious_dir = tmp_path / "malicious"
    malicious_dir.mkdir()
    (malicious_dir / "ok.py").write_text(VALID_OK, encoding="utf-8")
    sys.path.insert(0, str(malicious_dir))
    importlib.import_module("ok")

    result = ok_setup.probe_frontpanel_import(str(tmp_path / "cache"))

    assert result["ok_module"] is None
    assert result["ok_imported"] is False
    assert "untrusted ok module path" in result["ok_error"]


def test_probe_frontpanel_import_restores_sys_path_after_success(tmp_path):
    cache_dir = _write_frontpanel_cache(tmp_path / "cache")
    original_path = list(sys.path)

    result = ok_setup.probe_frontpanel_import(str(cache_dir))

    assert result["ok_imported"] is True
    assert os.path.samefile(result["ok_module"].__file__, cache_dir / "ok.py")
    assert sys.path == original_path


def test_probe_frontpanel_import_restores_sys_path_after_failure(tmp_path):
    original_path = list(sys.path)

    result = ok_setup.probe_frontpanel_import(str(tmp_path / "missing-cache"))

    assert result["ok_imported"] is False
    assert result["_ok_imported"] is False
    assert sys.path == original_path


def test_copy_frontpanel_files_does_not_mutate_sys_path(monkeypatch, tmp_path):
    sdk_dir = _write_frontpanel_sdk(tmp_path / "sdk")
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(ok_setup.os, "name", "nt")
    original_path = list(sys.path)

    copied_dir = ok_setup.copy_frontpanel_files(
        frontpanel_dir=str(sdk_dir),
        lib_dir=str(cache_dir),
    )

    assert copied_dir == ok_setup.resolve_path(str(cache_dir))
    assert (cache_dir / "ok.py").is_file()
    assert (cache_dir / "_ok.pyd").is_file()
    assert (cache_dir / "okFrontPanel.dll").is_file()
    assert sys.path == original_path
