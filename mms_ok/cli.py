"""Command-line interface for mms_ok."""

import argparse
from typing import Optional, Sequence

from rich.console import Console

from . import __version__
from .doctor import run_doctor
from .ok_setup import (
    DEFAULT_FRONTPANEL_DIR,
    DEFAULT_LIB_DIR,
    copy_frontpanel_files,
    get_frontpanel_version,
    import_ok,
    reset_frontpanel_cache,
    resolve_path,
)


LOCK_GUIDANCE = (
    "Close or restart Python processes, IPython/Jupyter kernels, notebooks, IDE "
    "terminals, or anything importing ok/_ok.pyd, then retry."
)

def _run_bist(_args) -> int:
    from . import BIST

    BIST().run_test()
    return 0


def _setup_frontpanel(_args) -> int:
    target_dir = copy_frontpanel_files()
    message = (
        f"FrontPanel files copied to: {target_dir}"
        if target_dir
        else "FrontPanel setup failed."
    )
    print(message)
    return 0 if target_dir is not None else 1


def _show_version(_args) -> int:
    print(f"v{__version__}")
    return 0


def _check_sdk(_args) -> int:
    try:
        ok = import_ok()
    except ImportError:
        print("FrontPanel SDK is not available.")
        return 1

    print(f"FrontPanel SDK is available.")
    print(f"FrontPanel SDK version: {get_frontpanel_version(ok)}")
    return 0


def _run_doctor(args) -> int:
    return run_doctor(
        frontpanel_dir=args.frontpanel_dir,
        lib_dir=args.lib_dir,
    )


def _reset_cache(args) -> int:
    frontpanel_dir = resolve_path(args.frontpanel_dir)
    lib_dir = resolve_path(args.lib_dir)
    console = Console()

    try:
        target_dir = reset_frontpanel_cache(
            frontpanel_dir=frontpanel_dir,
            lib_dir=lib_dir,
        )
    except PermissionError as exc:
        console.print("FrontPanel cache refresh failed: {}".format(exc))
        console.print(LOCK_GUIDANCE)
        return 1
    except FileNotFoundError as exc:
        console.print("FrontPanel SDK files were not found: {}".format(exc))
        console.print(
            "Checked SDK path: {}. Install the SDK or pass --frontpanel-dir.".format(
                frontpanel_dir
            )
        )
        return 1

    if target_dir is None:
        console.print("FrontPanel cache refresh failed.")
        console.print("Checked SDK path: {}".format(frontpanel_dir))
        console.print("Resolved cache path: {}".format(lib_dir))
        return 1

    console.print("FrontPanel cache refreshed: {}".format(target_dir))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mms_ok")
    subparsers = parser.add_subparsers(dest="command")

    bist_parser = subparsers.add_parser("bist", help="Run the built-in self-test")
    bist_parser.set_defaults(handler=_run_bist)

    version_parser = subparsers.add_parser("version", help="Show package version")
    version_parser.set_defaults(handler=_show_version)

    check_sdk_parser = subparsers.add_parser(
        "check-sdk",
        help="Check whether the FrontPanel SDK can be imported",
    )
    check_sdk_parser.set_defaults(handler=_check_sdk)

    setup_parser = subparsers.add_parser(
        "setup-frontpanel",
        help="Copy FrontPanel Python files into the default local directory",
    )
    setup_parser.set_defaults(handler=_setup_frontpanel)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose FrontPanel SDK setup and runtime visibility",
    )
    doctor_parser.add_argument(
        "--frontpanel-dir",
        default=DEFAULT_FRONTPANEL_DIR,
        help="FrontPanel SDK directory to inspect",
    )
    doctor_parser.add_argument(
        "--lib-dir",
        default=DEFAULT_LIB_DIR,
        help="Local FrontPanel cache directory to inspect",
    )
    doctor_parser.set_defaults(handler=_run_doctor)

    reset_cache_parser = subparsers.add_parser(
        "reset-cache",
        help="Refresh cached FrontPanel Python files",
    )
    reset_cache_parser.add_argument(
        "--frontpanel-dir",
        default=DEFAULT_FRONTPANEL_DIR,
        help="FrontPanel SDK directory to copy from",
    )
    reset_cache_parser.add_argument(
        "--lib-dir",
        default=DEFAULT_LIB_DIR,
        help="Local FrontPanel cache directory to refresh",
    )
    reset_cache_parser.set_defaults(handler=_reset_cache)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    return args.handler(args)
