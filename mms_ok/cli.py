"""Command-line interface for mms_ok."""

import argparse
from typing import Optional, Sequence

from . import __version__
from .ok_setup import copy_frontpanel_files, import_ok


def _run_bist(_args) -> int:
    from . import BIST

    BIST().run_test()
    return 0


def _setup_frontpanel(_args) -> int:
    target_dir = copy_frontpanel_files()
    return 0 if target_dir is not None else 1


def _show_version(_args) -> int:
    print(f"v{__version__}")
    return 0


def _check_sdk(_args) -> int:
    try:
        import_ok()
    except ImportError:
        print("FrontPanel SDK is not available.")
        return 1

    print(f"FrontPanel SDK is available (v{__version__}).")
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

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    return args.handler(args)
