from __future__ import annotations

import importlib
import os
import sys

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


@pytest.fixture(autouse=True)
def isolate_ok_import_state():
    old_path = list(sys.path)
    sentinel = object()
    old_modules = {
        name: sys.modules.get(name, sentinel)
        for name in ("ok", "_ok")
    }

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

    ok = ok_setup.import_ok()

    assert os.path.samefile(ok.__file__, cache_dir / "ok.py")
    assert "malicious" not in ok.__file__


def test_import_ok_accepts_trusted_cache_with_frontpanel_symbols(monkeypatch, tmp_path):
    cache_dir = _write_frontpanel_cache(tmp_path / "cache")
    monkeypatch.setattr(ok_setup, "DEFAULT_LIB_DIR", str(cache_dir))

    ok = ok_setup.import_ok()

    assert os.path.samefile(ok.__file__, cache_dir / "ok.py")
    assert hasattr(ok, "okCFrontPanel")
    assert ok.okCFrontPanel.GetAPIVersionString() == "1.2.3"


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
