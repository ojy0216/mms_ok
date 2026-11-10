"""Source isolation and macOS SDK/wheel/cache precedence without vendor binaries."""

import importlib
import os
import sys
import types
from pathlib import Path

import pytest

from mms_ok import cli, doctor, ok_setup


BINDING = '''
import sys, types
native = types.ModuleType(NATIVE_NAME)
native.__file__ = NATIVE_PATH
sys.modules[NATIVE_NAME] = native
class okCFrontPanel:
    @staticmethod
    def GetAPIVersionString():
        return "6.1.0"
class FrontPanelDevices:
    def GetCount(self):
        return 0
'''


def write_binding(path, native_path, native_name='_ok', bad_native=None):
    source = BINDING.replace('NATIVE_NAME', repr(native_name)).replace('NATIVE_PATH', repr(str(bad_native or native_path)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    native_path.write_bytes(b'native placeholder')


def make_sdk(path):
    python = path / 'API' / 'Python'
    write_binding(python / 'ok.py', python / '_ok.so')
    (path / 'API' / 'libokFrontPanel.2.dylib').write_bytes(b'dylib placeholder')
    return path


def make_cache(path):
    write_binding(path / 'ok.py', path / '_ok.so')
    (path / 'libokFrontPanel.2.dylib').write_bytes(b'dylib placeholder')
    return path


def make_wheel(path, monkeypatch):
    package = path / 'site-packages' / 'ok'
    write_binding(package / 'ok.py', package / '_ok.abi3.so', 'ok._ok')
    (package / '__init__.py').write_text('from .ok import *\n')
    dist = types.SimpleNamespace(
        files=['ok/__init__.py', 'ok/ok.py', 'ok/_ok.abi3.so'], version='6.1.0',
        locate_file=lambda name: package.parent / name,
    )
    monkeypatch.setattr(ok_setup.metadata, 'distribution', lambda name: dist)
    return package


@pytest.fixture(autouse=True)
def isolated_macos(monkeypatch, tmp_path):
    saved = {k: v for k, v in sys.modules.items() if k in ('ok', '_ok') or k.startswith('ok.')}
    saved_sdk = ok_setup._ok_module
    old_path = sys.path[:]
    ok_setup._clear_frontpanel_modules()
    monkeypatch.setattr(ok_setup, '_is_macos', lambda: True)
    monkeypatch.setattr(doctor, '_is_macos', lambda: True)
    monkeypatch.setattr(cli, '_is_macos', lambda: True)
    monkeypatch.setattr(ok_setup, 'DEFAULT_LIB_DIR', str(tmp_path / 'default-cache'))
    monkeypatch.delenv('MMS_OK_FRONTPANEL_DIR', raising=False)

    def no_wheel(name):
        raise ok_setup.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(ok_setup.metadata, 'distribution', no_wheel)
    yield
    ok_setup._clear_frontpanel_modules()
    sys.modules.update(saved)
    ok_setup._ok_module = saved_sdk
    sys.path[:] = old_path


def test_no_sdk_has_actionable_error_and_restores_path():
    original = sys.path[:]
    with pytest.raises(ImportError, match='Import ok failed.*Missing FrontPanel'):
        ok_setup.import_ok()
    assert sys.path == original
    assert 'ok' not in sys.modules


def test_official_wheel_without_sdk_folder_passes_doctor(monkeypatch, tmp_path, capsys):
    package = make_wheel(tmp_path, monkeypatch)
    result = ok_setup.probe_frontpanel_import()
    assert result['source'] == 'wheel'
    assert result['native_path'] == str(package / '_ok.abi3.so')
    assert result['_ok_imported']
    assert doctor.run_doctor(None, str(tmp_path / 'no-cache')) == 0
    output = capsys.readouterr().out
    assert '6.1.0' in output and 'PASS' in output
    assert 'Python runtime' in output
    assert '_ok.pyd' not in output and 'DLL' not in output


def test_explicit_sdk_precedes_loaded_wheel_and_cache(monkeypatch, tmp_path):
    make_wheel(tmp_path, monkeypatch)
    cache = make_cache(tmp_path / 'cache')
    assert ok_setup.probe_frontpanel_import(str(cache))['source'] == 'wheel'
    sdk = make_sdk(tmp_path / 'sdk')
    result = ok_setup.probe_frontpanel_import(str(cache), str(sdk))
    assert result['source'] == 'sdk'
    assert result['ok_path'] == str(sdk / 'API' / 'Python' / 'ok.py')
    assert result['_ok_imported']
    assert 'ok._ok' not in sys.modules


def test_env_path_and_direct_python_directory(monkeypatch, tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    monkeypatch.setenv('MMS_OK_FRONTPANEL_DIR', str(sdk))
    assert ok_setup.import_ok().__file__ == str(sdk / 'API' / 'Python' / 'ok.py')
    ok_setup._clear_frontpanel_modules()
    assert ok_setup.import_ok(str(sdk / 'API' / 'Python')).__file__ == str(sdk / 'API' / 'Python' / 'ok.py')


def test_explicit_path_wins_over_environment(monkeypatch, tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    other = make_sdk(tmp_path / 'other')
    monkeypatch.setenv('MMS_OK_FRONTPANEL_DIR', str(other))
    assert ok_setup.import_ok(str(sdk)).__file__ == str(sdk / 'API' / 'Python' / 'ok.py')


def test_cache_fallback_and_path_restoration(tmp_path):
    cache = make_cache(tmp_path / 'cache')
    old_path = sys.path[:]
    result = ok_setup.probe_frontpanel_import(str(cache))
    assert result['source'] == 'cache' and result['_ok_imported']
    assert sys.path == old_path


def test_missing_dylib_is_reported_and_not_imported(tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    (sdk / 'API' / 'libokFrontPanel.2.dylib').unlink()
    result = ok_setup.probe_frontpanel_import(frontpanel_dir=str(sdk))
    assert not result['ok_imported']
    assert 'libokFrontPanel.2.dylib' in result['ok_error']
    assert 'ok' not in sys.modules
    with pytest.raises(FileNotFoundError, match='libokFrontPanel.2.dylib'):
        ok_setup.copy_frontpanel_files(str(sdk), str(tmp_path / 'out'), raise_errors=True)
    assert not (tmp_path / 'out').exists()


def test_missing_sdk_falls_back_to_wheel_with_failure_details(monkeypatch, tmp_path):
    make_wheel(tmp_path, monkeypatch)
    result = ok_setup.probe_frontpanel_import(frontpanel_dir=str(tmp_path / 'missing'))
    assert result['source'] == 'wheel'
    assert any('sdk:' in attempt and 'Missing' in attempt for attempt in result['attempts'])


def test_python_before_311_reports_sdk_requirement(monkeypatch, tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    monkeypatch.setattr(ok_setup.sys, 'version_info', (3, 10, 0))
    result = ok_setup.probe_frontpanel_import(frontpanel_dir=str(sdk))
    assert not result['ok_imported']
    assert 'requires Python 3.11' in result['ok_error']
    assert 'ok' not in sys.modules


def test_native_architecture_failure_keeps_original_reason(tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    (sdk / 'API' / 'Python' / 'ok.py').write_text('raise ImportError("mach-o file, but is an incompatible architecture")')
    old_path = sys.path[:]
    result = ok_setup.probe_frontpanel_import(frontpanel_dir=str(sdk))
    assert 'incompatible architecture' in result['ok_error']
    assert not result['_ok_imported']
    assert sys.path == old_path
    assert 'ok' not in sys.modules


def test_untrusted_python_and_preloaded_native_do_not_win(tmp_path, monkeypatch):
    sdk = make_sdk(tmp_path / 'sdk')
    other = tmp_path / 'untrusted'
    other.mkdir()
    (other / 'ok.py').write_text('raise AssertionError("untrusted ok.py executed")')
    (other / '_ok.py').write_text('raise AssertionError("untrusted _ok.py executed")')
    monkeypatch.syspath_prepend(str(other))
    rogue = types.ModuleType('_ok')
    rogue.__file__ = str(other / '_ok.so')
    sys.modules['_ok'] = rogue
    original = sys.path[:]
    module = ok_setup.import_ok(str(sdk))
    assert module.__file__ == str(sdk / 'API' / 'Python' / 'ok.py')
    assert sys.modules['_ok'] is not rogue
    assert sys.path == original


def test_rejects_native_path_mismatch_after_import(tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    python = sdk / 'API' / 'Python'
    write_binding(python / 'ok.py', python / '_ok.so', bad_native=tmp_path / 'untrusted.so')
    result = ok_setup.probe_frontpanel_import(frontpanel_dir=str(sdk))
    assert not result['ok_imported']
    assert 'untrusted _ok module path' in result['ok_error']
    assert 'ok' not in sys.modules and '_ok' not in sys.modules


def test_unrelated_installed_ok_package_is_rejected(monkeypatch, tmp_path):
    package = make_wheel(tmp_path, monkeypatch)
    (package / 'ok.py').write_text('class Unrelated: pass')
    result = ok_setup.probe_frontpanel_import()
    assert not result['ok_imported']
    assert 'missing okCFrontPanel' in result['ok_error']


def test_cache_copy_preserves_dylib_and_refreshes_partial_cache(tmp_path):
    sdk = make_sdk(tmp_path / 'sdk')
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / 'ok.py').write_text('stale')
    old_path = sys.path[:]
    assert ok_setup.copy_frontpanel_files(str(sdk), str(cache)) == str(cache)
    assert ok_setup.frontpanel_cache_status(str(cache))['complete']
    assert (cache / 'libokFrontPanel.2.dylib').read_bytes() == b'dylib placeholder'
    assert (cache / 'ok.py').read_text() != 'stale'
    assert sys.path == old_path


def test_setup_cli_uses_selected_paths(tmp_path, capsys):
    sdk = make_sdk(tmp_path / 'sdk')
    cache = tmp_path / 'custom-cache'
    assert cli.main(['setup-frontpanel', '--frontpanel-dir', str(sdk), '--lib-dir', str(cache)]) == 0
    assert ok_setup.frontpanel_cache_status(str(cache))['complete']
    assert str(cache) in capsys.readouterr().out


def test_doctor_probes_the_requested_sdk_not_the_default(tmp_path, capsys):
    sdk = make_sdk(tmp_path / 'only-this-sdk')
    assert cli.main(['doctor', '--frontpanel-dir', str(sdk), '--lib-dir', str(tmp_path / 'missing')]) == 0
    assert sys.modules['ok'].__file__ == str(sdk / 'API' / 'Python' / 'ok.py')
    assert 'Source: sdk' in capsys.readouterr().out
