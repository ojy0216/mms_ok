"""Command-line interface for mms_ok."""

import argparse
import os
import sys
from typing import Optional, Sequence

from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .devices import (
    DeviceDiscoveryError,
    FrontPanelUnavailableError,
    list_devices,
)
from .display import MMS_OK_LOGO
from .doctor import run_doctor
from .ok_setup import (
    DEFAULT_FRONTPANEL_DIR,
    DEFAULT_LIB_DIR,
    copy_frontpanel_files,
    frontpanel_cache_status,
    get_frontpanel_version,
    import_ok,
    reset_frontpanel_cache,
    resolve_path,
)


LOCK_GUIDANCE = (
    "Close or restart Python processes, IPython/Jupyter kernels, notebooks, IDE "
    "terminals, or anything importing ok/_ok.pyd, then retry."
)

EXIT_SDK_UNAVAILABLE = 1
EXIT_NO_DEVICES = 2
EXIT_DISCOVERY_ERROR = 3
EXIT_BIST_FAILED = 4


MENU_COMMANDS = (
    ("doctor", "Inspect SDK, cache, and Jupyter visibility"),
    ("check-sdk", "Verify FrontPanel import"),
    ("setup-frontpanel", "Copy SDK Python files"),
    ("devices", "List connected boards"),
    ("bist", "Run board self-test"),
)

KEY_UP = "up"
KEY_DOWN = "down"
KEY_ENTER = "enter"
KEY_QUIT = "quit"
KEY_UNKNOWN = "unknown"


def _run_bist(_args) -> int:
    from . import BIST

    return 0 if BIST().run_test() else EXIT_BIST_FAILED


def _setup_frontpanel(_args) -> int:
    cache = frontpanel_cache_status(DEFAULT_LIB_DIR)
    if cache["complete"]:
        print(f"FrontPanel files already set up at: {cache['path']}")
        return 0

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


def _list_devices(_args) -> int:
    console = Console()

    try:
        devices = list_devices()
    except FrontPanelUnavailableError as exc:
        console.print(str(exc))
        return EXIT_SDK_UNAVAILABLE
    except DeviceDiscoveryError as exc:
        console.print(str(exc))
        return EXIT_DISCOVERY_ERROR

    if not devices:
        console.print("No Opal Kelly FrontPanel devices found.")
        return EXIT_NO_DEVICES

    table = Table(title="Opal Kelly Devices")
    table.add_column("device_id")
    table.add_column("model")
    table.add_column("serial")

    for device in devices:
        table.add_row(
            device.device_id,
            device.model,
            device.serial,
        )

    console.print(table)
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

    devices_parser = subparsers.add_parser(
        "devices",
        help="List attached Opal Kelly FrontPanel devices",
    )
    devices_parser.set_defaults(handler=_list_devices)

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


def _read_menu_key() -> str:
    if os.name == "nt" and sys.stdin.isatty():
        import msvcrt

        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            key = msvcrt.getwch()
            if key == "H":
                return KEY_UP
            if key == "P":
                return KEY_DOWN
            return KEY_UNKNOWN
    elif sys.stdin.isatty():
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)
            if key == "\x1b":
                ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                if ready:
                    sequence = sys.stdin.read(2)
                    if sequence == "[A":
                        return KEY_UP
                    if sequence == "[B":
                        return KEY_DOWN
                return KEY_QUIT
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, settings)
    else:
        key = sys.stdin.read(1)
        if key == "":
            raise EOFError
        if key == "\x1b":
            sequence = sys.stdin.read(2)
            if sequence == "[A":
                return KEY_UP
            if sequence == "[B":
                return KEY_DOWN
            return KEY_QUIT

    if key in ("\r", "\n"):
        return KEY_ENTER
    if key in ("q", "Q", "\x1b", "\x03"):
        return KEY_QUIT
    return KEY_UNKNOWN


def _render_interactive_menu(console: Console, selected: int, message: str = "") -> None:
    console.clear()
    console.print(MMS_OK_LOGO, style="bold white")
    console.print()
    console.print(Text("https://github.com/ojy0216/mms_ok", style="white"))
    console.print("FrontPanel setup and board diagnostics.")
    console.print()
    title_line = Text()
    title_line.append("mms_ok setup helper", style="bold")
    title_line.append(f"  v{__version__}", style="dim")
    console.print(title_line)

    for index, (command, description) in enumerate(MENU_COMMANDS):
        pointer = ">" if index == selected else " "
        command_style = "bold cyan" if index == selected else "bold white"
        description_style = "cyan" if index == selected else "white"
        console.print(
            f"{pointer} {index + 1}. ",
            f"[{command_style}]{command:<17}[/] ",
            f"[{description_style}]{description}[/]",
            sep="",
        )

    console.print()
    console.print("[dim]Up/Down  |  Enter Run  |  Q Quit[/dim]")

    if message:
        console.print()
        console.print(message, style="yellow")


def _run_interactive_menu() -> int:
    console = Console(highlight=False)
    selected = 0
    message = ""

    while True:
        _render_interactive_menu(console, selected, message)
        try:
            key = _read_menu_key()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return 0

        if key == KEY_QUIT:
            return 0
        if key == KEY_UP:
            selected = (selected - 1) % len(MENU_COMMANDS)
            message = ""
            continue
        if key == KEY_DOWN:
            selected = (selected + 1) % len(MENU_COMMANDS)
            message = ""
            continue
        if key == KEY_ENTER:
            command = MENU_COMMANDS[selected][0]
            console.clear()
            return main([command])

        message = "Use the arrow keys, Enter, or q."


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) == 0:
        return _run_interactive_menu()

    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    return args.handler(args)
