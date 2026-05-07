from __future__ import annotations

import os

import pytest

from mms_ok import cli
from mms_ok import doctor


class FakeFrontPanel:
    def GetDeviceCount(self) -> int:
        return 2


class EmptyFrontPanel:
    def GetDeviceCount(self) -> int:
        return 0


class FakeOk:
    okCFrontPanel = FakeFrontPanel


class EmptyOk:
    okCFrontPanel = EmptyFrontPanel


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


def test_bare_cli_renders_interactive_menu(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_read_menu_key", lambda: cli.KEY_QUIT)

    status = cli.main([])

    captured = capsys.readouterr()
    assert status == 0
    assert "mms_ok setup helper" in captured.out
    assert "check-sdk" in captured.out
    assert "setup-frontpanel" in captured.out
    assert "doctor" in captured.out
    assert "bist" in captured.out
    assert "version" not in captured.out


def test_bare_cli_menu_dispatches_selected_command(monkeypatch):
    calls = []

    def fake_doctor(args):
        calls.append(args.command)
        return 17

    monkeypatch.setattr(cli, "_read_menu_key", lambda: cli.KEY_ENTER)
    monkeypatch.setattr(cli, "_run_doctor", fake_doctor)

    status = cli.main([])

    assert status == 17
    assert calls == ["doctor"]


def test_bare_cli_menu_arrow_selection_dispatches_command(monkeypatch):
    calls = []
    keys = iter([cli.KEY_DOWN, cli.KEY_DOWN, cli.KEY_ENTER])

    def fake_setup_frontpanel(args):
        calls.append(args.command)
        return 23

    monkeypatch.setattr(cli, "_read_menu_key", lambda: next(keys))
    monkeypatch.setattr(cli, "_setup_frontpanel", fake_setup_frontpanel)

    status = cli.main([])

    assert status == 23
    assert calls == ["setup-frontpanel"]


def test_bare_cli_menu_quit_exits_cleanly(monkeypatch):
    monkeypatch.setattr(cli, "_read_menu_key", lambda: cli.KEY_QUIT)

    assert cli.main([]) == 0


def test_bare_cli_menu_eof_exits_cleanly(monkeypatch):
    def raise_eof():
        raise EOFError

    monkeypatch.setattr(cli, "_read_menu_key", raise_eof)

    assert cli.main([]) == 0


def test_bare_cli_menu_keyboard_interrupt_exits_cleanly(monkeypatch):
    def raise_keyboard_interrupt():
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_read_menu_key", raise_keyboard_interrupt)

    assert cli.main([]) == 0


def test_bare_cli_menu_invalid_input_reprompts_without_traceback(monkeypatch, capsys):
    keys = iter([cli.KEY_UNKNOWN, cli.KEY_QUIT])
    monkeypatch.setattr(cli, "_read_menu_key", lambda: next(keys))

    status = cli.main([])

    captured = capsys.readouterr()
    assert status == 0
    assert "Use the arrow keys, Enter, or q." in captured.out


def test_existing_version_subcommand_still_dispatches(capsys):
    status = cli.main(["version"])

    captured = capsys.readouterr()
    assert status == 0
    assert captured.out == f"v{cli.__version__}\n"


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


@pytest.mark.parametrize(
    ("sdk_exists", "cache", "probe"),
    [
        (
            False,
            lambda path: _cache(path),
            {
                "ok_module": FakeOk,
                "ok_imported": True,
                "_ok_imported": True,
                "ok_error": None,
                "_ok_error": None,
                "used_cache_path": True,
            },
        ),
        (
            True,
            lambda path: _cache(path),
            {
                "ok_module": FakeOk,
                "ok_imported": True,
                "_ok_imported": False,
                "ok_error": None,
                "_ok_error": "ImportError: DLL load failed",
                "used_cache_path": True,
            },
        ),
    ],
)
def test_doctor_fails_when_setup_rows_fail_even_if_ok_import_succeeds(
    monkeypatch, tmp_path, capsys, sdk_exists, cache, probe
):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: sdk_exists)
    monkeypatch.setattr(doctor, "frontpanel_cache_status", cache)
    monkeypatch.setattr(doctor, "probe_frontpanel_import", lambda path: probe)
    monkeypatch.setattr(doctor, "get_frontpanel_version", lambda ok: "9.9.9")

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    captured = capsys.readouterr()
    assert status == 1
    assert "ok import" in captured.out
    assert "imported" in captured.out


def test_doctor_allows_missing_optional_cache_when_imports_and_api_work(
    monkeypatch, tmp_path, capsys
):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: path == sdk_dir)
    monkeypatch.setattr(
        doctor, "frontpanel_cache_status", lambda path: _cache(path, complete=False)
    )
    monkeypatch.setattr(
        doctor,
        "probe_frontpanel_import",
        lambda path: {
            "ok_module": FakeOk,
            "ok_imported": True,
            "_ok_imported": True,
            "ok_error": None,
            "_ok_error": None,
            "used_cache_path": False,
        },
    )
    monkeypatch.setattr(doctor, "get_frontpanel_version", lambda ok: "9.9.9")

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    captured = capsys.readouterr()
    assert status == 0
    assert "Local cache" in captured.out
    assert "Optional local cache is not complete" in captured.out
    assert "ok import" in captured.out
    assert "imported" in captured.out


def test_doctor_warning_only_zero_devices_exits_success(
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
            "ok_module": EmptyOk,
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
    assert "Device count" in captured.out
    assert "0" in captured.out


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


def test_setup_frontpanel_reports_existing_complete_cache(
    monkeypatch, tmp_path, capsys
):
    lib_dir = str(tmp_path / "cache")

    def fail_copy():
        raise AssertionError("copy_frontpanel_files should not be called")

    monkeypatch.setattr(cli, "frontpanel_cache_status", lambda path: _cache(lib_dir))
    monkeypatch.setattr(cli, "copy_frontpanel_files", fail_copy)

    status = cli.main(["setup-frontpanel"])

    captured = capsys.readouterr()
    assert status == 0
    assert "already set up" in captured.out
    assert "FrontPanel files copied" not in captured.out
    assert lib_dir in captured.out


def test_setup_frontpanel_reports_copy_when_cache_is_missing(
    monkeypatch, tmp_path, capsys
):
    lib_dir = str(tmp_path / "cache")

    monkeypatch.setattr(
        cli, "frontpanel_cache_status", lambda path: _cache(lib_dir, complete=False)
    )
    monkeypatch.setattr(cli, "copy_frontpanel_files", lambda: lib_dir)

    status = cli.main(["setup-frontpanel"])

    captured = capsys.readouterr()
    assert status == 0
    assert "FrontPanel files copied to:" in captured.out
    assert lib_dir in captured.out
