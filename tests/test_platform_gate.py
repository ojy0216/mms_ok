from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_python(code: str, env: Optional[dict] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_python_as_non_windows(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MMS_OK_UNSUPPORTED_PLATFORM_SIGNAL"] = "posix"
    return _run_python(code, env=env)


def _assert_platform_gate_failure(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 1
    assert "CRITICAL" in result.stderr
    assert "\033[" not in result.stderr
    assert "mms_ok" in result.stderr
    assert "Windows-only" in result.stderr
    assert "unsupported platform" in result.stderr


def test_non_windows_package_import_fails_fast() -> None:
    result = _run_python_as_non_windows("import mms_ok")

    _assert_platform_gate_failure(result)


def test_non_windows_module_execution_fails_before_menu() -> None:
    result = _run_python_as_non_windows(
        "import runpy\n"
        "runpy.run_module('mms_ok', run_name='__main__', alter_sys=True)"
    )

    _assert_platform_gate_failure(result)
    assert "mms_ok setup helper" not in result.stdout


def test_console_script_import_path_inherits_package_gate() -> None:
    result = _run_python_as_non_windows(
        "from mms_ok.cli import main; raise SystemExit(main(['version']))"
    )

    _assert_platform_gate_failure(result)
    assert "v" not in result.stdout


def test_metadata_lookup_does_not_import_or_gate_package() -> None:
    result = _run_python(
        "try:\n"
        "    import importlib.metadata as m\n"
        "except ImportError:\n"
        "    import importlib_metadata as m\n"
        "print(m.version('mms_ok'))"
    )

    assert result.returncode == 0
    assert result.stdout.strip()
    assert "CRITICAL" not in result.stderr
    assert "Windows-only" not in result.stderr


def test_windows_simulated_public_api_and_cli_parser_import() -> None:
    result = _run_python(
        "import os\n"
        "from loguru import logger as _logger\n"
        "original = os.name\n"
        "os.name = 'nt'\n"
        "try:\n"
        "    import mms_ok\n"
        "    expected = {'BIST', 'XEM7310', 'XEM7360', 'list_devices', "
        "'copy_frontpanel_files', 'setup_frontpanel', '__version__'}\n"
        "    missing = expected.difference(dir(mms_ok))\n"
        "    import mms_ok.cli as cli\n"
        "    parser = cli.build_parser()\n"
        "    assert parser.prog == 'mms_ok'\n"
        "    assert not missing, missing\n"
        "finally:\n"
        "    os.name = original\n"
    )

    assert result.returncode == 0, result.stderr


def test_windows_simulated_import_does_not_require_colorama() -> None:
    result = _run_python(
        "import os\n"
        "import sys\n"
        "from loguru import logger as _logger\n"
        "\n"
        "class BlockColorama:\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'colorama' or fullname.startswith('colorama.'):\n"
        "            raise ModuleNotFoundError(\"No module named 'colorama'\")\n"
        "        return None\n"
        "\n"
        "sys.modules.pop('colorama', None)\n"
        "sys.meta_path.insert(0, BlockColorama())\n"
        "original = os.name\n"
        "os.name = 'nt'\n"
        "try:\n"
        "    import mms_ok\n"
        "    assert 'BIST' in dir(mms_ok)\n"
        "finally:\n"
        "    os.name = original\n"
    )

    assert result.returncode == 0, result.stderr


def test_windows_simulated_fpga_facade_import_identities() -> None:
    result = _run_python(
        "import os\n"
        "from loguru import logger as _logger\n"
        "original = os.name\n"
        "os.name = 'nt'\n"
        "try:\n"
        "    import mms_ok\n"
        "    from mms_ok import fpga\n"
        "    from mms_ok.fpga_base import XEM\n"
        "    from mms_ok.fpga_xem7310 import XEM7310\n"
        "    from mms_ok.fpga_xem7360 import XEM7360\n"
        "    assert fpga.XEM is XEM\n"
        "    assert fpga.XEM7310 is XEM7310\n"
        "    assert fpga.XEM7360 is XEM7360\n"
        "    assert mms_ok.XEM7310 is XEM7310\n"
        "    assert mms_ok.XEM7360 is XEM7360\n"
        "finally:\n"
        "    os.name = original\n"
    )

    assert result.returncode == 0, result.stderr


def test_platform_gate_import_surface_is_safe() -> None:
    gate_path = PROJECT_ROOT / "mms_ok" / "_platform_gate.py"
    tree = ast.parse(gate_path.read_text())

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    assert imports == ["os", "sys"]

    source = gate_path.read_text()
    forbidden = [
        "diagnostics",
        "loguru",
        "ok_setup",
        "cli",
        "pathlib",
        "bist",
        "fpga",
        "devices",
        "FrontPanel",
    ]
    assert not any(name in source for name in forbidden)


def test_console_script_mapping_remains_package_cli_main() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert 'mms_ok = "mms_ok.cli:main"' in pyproject
    assert '"colorama"' not in pyproject
