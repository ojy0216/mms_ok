from __future__ import annotations

import os

import pytest

import mms_ok
from mms_ok import cli
from mms_ok import doctor, ok_setup


@pytest.fixture(autouse=True)
def windows_diagnostics(monkeypatch):
    for module in (cli, doctor, ok_setup):
        monkeypatch.setattr(module, "_is_macos", lambda: False)
    monkeypatch.delenv("MMS_OK_FRONTPANEL_DIR", raising=False)


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


def test_bist_subcommand_exits_success_when_bist_passes(monkeypatch):
    class PassingBIST:
        def run_test(self):
            return True

    monkeypatch.setattr(mms_ok, "BIST", PassingBIST)

    assert cli.main(["bist"]) == 0


def test_bist_subcommand_exits_failure_when_bist_fails(monkeypatch):
    class FailingBIST:
        def run_test(self):
            return False

    monkeypatch.setattr(mms_ok, "BIST", FailingBIST)

    assert cli.main(["bist"]) == cli.EXIT_BIST_FAILED


@pytest.mark.parametrize(
    ("is_macos", "mac_version", "machine", "os_name", "details"),
    [
        (False, "15.3.1", "AMD64", "Windows", "10.0.26300 (AMD64)"),
        (True, "15.3.1", "arm64", "macOS", "15.3.1 (arm64)"),
        (True, "15.3.1", "x86_64", "macOS", "15.3.1 (x86_64)"),
        (True, "", "arm64", "macOS", "24.3.0 (arm64)"),
    ],
    ids=["windows", "macos-arm64", "macos-x86_64", "macos-release-fallback"],
)
@pytest.mark.parametrize("sdk_available", [True, False], ids=["sdk-ok", "sdk-failed"])
def test_doctor_reports_operating_system(
    monkeypatch, tmp_path, capsys, is_macos, mac_version, machine,
    os_name, details, sdk_available,
):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")
    for module in (cli, doctor, ok_setup):
        monkeypatch.setattr(module, "_is_macos", lambda: is_macos)
    monkeypatch.setattr(doctor.platform, "version", lambda: "10.0.26300")
    monkeypatch.setattr(doctor.platform, "mac_ver", lambda: (mac_version, (), ""))
    monkeypatch.setattr(doctor.platform, "release", lambda: "24.3.0")
    monkeypatch.setattr(doctor.platform, "machine", lambda: machine)
    monkeypatch.setenv("COLUMNS", "240")
    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: sdk_available)
    cache = _cache(lib_dir, complete=sdk_available)
    if is_macos:
        cache["files"] = {
            name: {"path": os.path.join(lib_dir, name), "exists": sdk_available}
            for name in ("ok.py", "_ok.so", "libokFrontPanel.2.dylib")
        }
    monkeypatch.setattr(doctor, "frontpanel_cache_status", lambda path: cache)
    monkeypatch.setattr(
        doctor,
        "probe_frontpanel_import",
        lambda path, **kwargs: {
            "ok_module": FakeOk if sdk_available else None,
            "ok_imported": sdk_available,
            "_ok_imported": sdk_available,
            "ok_error": None if sdk_available else "ImportError: no module named ok",
            "_ok_error": None if sdk_available else "ImportError: no module named _ok",
            "used_cache_path": sdk_available,
        },
    )
    monkeypatch.setattr(doctor, "get_frontpanel_version", lambda ok: "9.9.9")

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    output = capsys.readouterr().out
    assert status == (0 if sdk_available else 1)
    lines = output.splitlines()
    os_index = next(i for i, line in enumerate(lines) if "Operating system" in line)
    assert "[O]" in lines[os_index]
    assert os_name in lines[os_index]
    assert details in lines[os_index]
    assert "Python runtime" in lines[os_index + 1]
    assert ("PASS" if sdk_available else "FAIL") in output


def test_doctor_success_reports_api_and_device_count(monkeypatch, tmp_path, capsys):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: path == sdk_dir)
    monkeypatch.setattr(doctor, "frontpanel_cache_status", lambda path: _cache(path))
    monkeypatch.setattr(
        doctor,
        "probe_frontpanel_import",
        lambda path, **kwargs: {
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
    assert "PASS" in captured.out
    assert "FAIL" not in captured.out


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
        lambda path, **kwargs: {
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
    assert "FAIL" in captured.out


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
        lambda path, **kwargs: {
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
def test_doctor_only_requires_importable_runtime_not_sdk_folder(
    monkeypatch, tmp_path, capsys, sdk_exists, cache, probe
):
    lib_dir = str(tmp_path / "cache")
    sdk_dir = str(tmp_path / "sdk")

    monkeypatch.setattr(doctor.os.path, "isdir", lambda path: sdk_exists)
    monkeypatch.setattr(doctor, "frontpanel_cache_status", cache)
    monkeypatch.setattr(doctor, "probe_frontpanel_import", lambda path, **kwargs: probe)
    monkeypatch.setattr(doctor, "get_frontpanel_version", lambda ok: "9.9.9")

    status = cli.main(["doctor", "--frontpanel-dir", sdk_dir, "--lib-dir", lib_dir])

    captured = capsys.readouterr()
    assert status == (0 if not sdk_exists else 1)
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
        lambda path, **kwargs: {
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
        lambda path, **kwargs: {
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
    assert "PASS" in captured.out
    assert "FAIL" not in captured.out


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
    monkeypatch.setattr(cli, "copy_frontpanel_files", lambda **kwargs: lib_dir)

    status = cli.main(["setup-frontpanel"])

    captured = capsys.readouterr()
    assert status == 0
    assert "FrontPanel files copied to:" in captured.out
    assert lib_dir in captured.out
