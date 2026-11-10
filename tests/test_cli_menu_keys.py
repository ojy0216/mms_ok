"""Exercise terminal input rather than replacing the menu's key reader."""

import os
import sys
from types import SimpleNamespace

import pytest

from mms_ok import cli


@pytest.fixture
def posix_terminal(monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX pseudo-terminal required")

    import pty
    import signal
    import termios
    import tty

    master_fd, slave_fd = pty.openpty()
    try:
        with os.fdopen(slave_fd, "r", encoding="utf-8") as stdin:
            def terminal_settings():
                settings = termios.tcgetattr(stdin.fileno())
                # macOS sets PENDIN when switching back to canonical mode.
                settings[3] &= ~getattr(termios, "PENDIN", 0)
                return settings

            settings = terminal_settings()
            pending = []
            setraw = tty.setraw

            def feed_after_setraw(fd):
                # Check restoration between successive menu reads, too.
                assert terminal_settings() == settings
                setraw(fd)
                assert pending, "Unexpected terminal read"
                # Queue the entire sequence to reproduce TextIO read-ahead.
                os.write(master_fd, pending.pop(0))

            monkeypatch.setattr(tty, "setraw", feed_after_setraw)
            monkeypatch.setattr(
                cli, "sys", SimpleNamespace(stdin=stdin, argv=["mms_ok"])
            )

            def read_timeout(_signum, _frame):
                pytest.fail("Terminal input did not complete within five seconds")

            previous_handler = signal.signal(signal.SIGALRM, read_timeout)
            signal.alarm(5)
            try:
                yield pending
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)
            assert terminal_settings() == settings
            assert not pending, "Not all terminal input was consumed"
    finally:
        os.close(master_fd)


@pytest.mark.parametrize(
    "input_bytes, expected",
    [
        (b"\x1b[A", cli.KEY_UP),
        (b"\x1b[B", cli.KEY_DOWN),
        (b"\r", cli.KEY_ENTER),
        (b"\n", cli.KEY_ENTER),
        (b"q", cli.KEY_QUIT),
        (b"Q", cli.KEY_QUIT),
        (b"\x1b", cli.KEY_QUIT),
        (b"\x1b[", cli.KEY_QUIT),
        (b"\x03", cli.KEY_QUIT),
        (b"x", cli.KEY_UNKNOWN),
    ],
)
def test_posix_terminal_keys(posix_terminal, input_bytes, expected):
    posix_terminal.append(input_bytes)

    assert cli._read_menu_key() == expected


def test_bare_menu_navigates_and_runs_command_in_terminal(
    posix_terminal, monkeypatch
):
    posix_terminal.extend([b"\x1b[B", b"\x1b[B", b"\x1b[A", b"\r"])
    selected_indices = []
    commands = []
    render = cli._render_interactive_menu

    def record_selection(console, selected, message=""):
        selected_indices.append(selected)
        render(console, selected, message)

    def check_sdk(args):
        commands.append(args.command)
        return 23

    monkeypatch.setattr(cli, "_render_interactive_menu", record_selection)
    monkeypatch.setattr(cli, "_check_sdk", check_sdk)

    assert cli.main() == 23
    assert selected_indices == [0, 1, 2, 1]
    assert commands == ["check-sdk"]


def test_bare_menu_escape_exits_in_terminal(posix_terminal):
    posix_terminal.append(b"\x1b")

    assert cli.main() == 0


@pytest.mark.parametrize("prefix", ["\x00", "\xe0"])
@pytest.mark.parametrize(
    "key, expected", [("H", cli.KEY_UP), ("P", cli.KEY_DOWN), ("K", cli.KEY_UNKNOWN)]
)
def test_windows_extended_keys(monkeypatch, prefix, key, expected):
    _assert_windows_key(monkeypatch, [prefix, key], expected)


@pytest.mark.parametrize(
    "key, expected",
    [
        ("\r", cli.KEY_ENTER),
        ("\n", cli.KEY_ENTER),
        ("q", cli.KEY_QUIT),
        ("Q", cli.KEY_QUIT),
        ("\x1b", cli.KEY_QUIT),
        ("\x03", cli.KEY_QUIT),
        ("x", cli.KEY_UNKNOWN),
    ],
)
def test_windows_regular_keys(monkeypatch, key, expected):
    _assert_windows_key(monkeypatch, [key], expected)


def _assert_windows_key(monkeypatch, keys, expected):
    inputs = iter(keys)
    monkeypatch.setattr(cli, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        cli, "sys", SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True))
    )
    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(getwch=lambda: next(inputs))
    )

    assert cli._read_menu_key() == expected
    assert list(inputs) == []
