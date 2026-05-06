from __future__ import annotations

import os

import pytest

from mms_ok import cli
from mms_ok import doctor


class FakeFrontPanel:
    def GetDeviceCount(self) -> int:
        return 2


class FakeOk:
    okCFrontPanel = FakeFrontPanel


class BrokenFrontPanel:
    def GetDeviceCount(self) -> int:
        raise RuntimeError("frontpanel unavailable")


class BrokenOk:
    okCFrontPanel = BrokenFrontPanel


def _cache(path, complete=True, partial=False):
    return {
        "path": path,
        "complete": complete,
        "partial": partial,
        "missing": not complete and not partial,
        "files": {
            "ok.py": {"path": os.path.join(path, "ok.py"), "exists": complete},
            "_ok.pyd": {"path": os.path.join(path, "_ok.pyd"), "exists": complete},
            "okFrontPanel.dll": {
                "path": os.path.join(path, "okFrontPanel.dll"),
                "exists": complete,
            },
        },
    }


def test_help_includes_diagnostics_commands(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "doctor" in captured.out
    assert "reset-cache" in captured.out


def test_doctor_success_reports_api_and_device_count(monkeypatch, tmp_path, capsys):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: path == sdk_dir)
    monkeypatch.setattr(doctor, "frontpanel_cache_status", lambda path: _cache(path))
    monkeypatch.setattr(
        doctor,
        "probe_frontpanel_import",
        lambda path: {
            "ok_module": FakeOk,
            "ok_imported": True,
            "_ok_imported": True,
            "ok_error": None,
            "_ok_error": None,
            "used_cache_path": True,
        },
    )
    monkeypatch.setattr(doctor, "get_frontpanel_version", lambda ok: "9.9.9")

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    captured = capsys.readouterr()
    assert status == 0
    assert "FrontPanel API" in captured.out
    assert "9.9.9" in captured.out
    assert "Device count" in captured.out
    assert "2" in captured.out


def test_doctor_failure_reports_guidance(monkeypatch, tmp_path, capsys):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "missing-sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: False)
    monkeypatch.setattr(
        doctor, "frontpanel_cache_status", lambda path: _cache(path, complete=False)
    )
    monkeypatch.setattr(
        doctor,
        "probe_frontpanel_import",
        lambda path: {
            "ok_module": None,
            "ok_imported": False,
            "_ok_imported": False,
            "ok_error": "ImportError: no module named ok",
            "_ok_error": "ImportError: no module named _ok",
            "used_cache_path": False,
        },
    )

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    captured = capsys.readouterr()
    assert status == 1
    assert "SDK path" in captured.out
    assert "missing" in captured.out
    assert "mms_ok reset-cache" in captured.out
    assert "64-bit Python" in captured.out


def test_doctor_fails_when_frontpanel_api_probe_fails(
    monkeypatch, tmp_path, capsys
):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: path == sdk_dir)
    monkeypatch.setattr(doctor, "frontpanel_cache_status", lambda path: _cache(path))
    monkeypatch.setattr(
        doctor,
        "probe_frontpanel_import",
        lambda path: {
            "ok_module": BrokenOk,
            "ok_imported": True,
            "_ok_imported": True,
            "ok_error": None,
            "_ok_error": None,
            "used_cache_path": True,
        },
    )
    monkeypatch.setattr(doctor, "get_frontpanel_version", lambda ok: "9.9.9")

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    captured = capsys.readouterr()
    assert status == 1
    assert "Device count" in captured.out
    assert "frontpanel unavailable" in captured.out
    assert "FrontPanel API probing failed" in captured.out


def test_reset_cache_uses_resolved_default_path(monkeypatch, capsys):
    calls = []

    def fake_reset(frontpanel_dir, lib_dir):
        calls.append((frontpanel_dir, lib_dir))
        return lib_dir

    monkeypatch.setattr(cli, "reset_frontpanel_cache", fake_reset)

    status = cli.main(["reset-cache"])

    captured = capsys.readouterr()
    assert status == 0
    assert calls == [
        (
            cli.resolve_path(cli.DEFAULT_FRONTPANEL_DIR),
            cli.resolve_path(cli.DEFAULT_LIB_DIR),
        )
    ]
    assert cli.resolve_path(cli.DEFAULT_LIB_DIR) in captured.out


def test_reset_cache_permission_error_reports_lock_guidance(monkeypatch, capsys):
    def locked(frontpanel_dir, lib_dir):
        raise PermissionError("file is locked")

    monkeypatch.setattr(cli, "reset_frontpanel_cache", locked)

    status = cli.main(["reset-cache"])

    captured = capsys.readouterr()
    assert status == 1
    assert "file is locked" in captured.out
    assert "IPython/Jupyter kernels" in captured.out
    assert "ok/_ok.pyd" in captured.out
