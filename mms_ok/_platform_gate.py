"""Import-safe platform enforcement for mms_ok runtime entry points."""

import os
import sys

_UNSUPPORTED_PLATFORM_EXIT_CODE = 1
_UNSUPPORTED_PLATFORM_SIGNAL_ENV = "MMS_OK_UNSUPPORTED_PLATFORM_SIGNAL"
_UNSUPPORTED_PLATFORM_MESSAGE = (
    "mms_ok is a Windows-only runtime package; "
    "unsupported platform signal: os.name={!r}."
)


def enforce_windows_runtime(critical=None) -> None:
    """Terminate early when mms_ok is imported outside Windows."""
    unsupported_signal = os.environ.get(_UNSUPPORTED_PLATFORM_SIGNAL_ENV)
    platform_signal = unsupported_signal or os.name
    if unsupported_signal is None and platform_signal == "nt":
        return

    message = _UNSUPPORTED_PLATFORM_MESSAGE.format(platform_signal)
    if critical is None:
        print("CRITICAL | {}".format(message), file=sys.stderr)
    else:
        critical(message)
    raise SystemExit(_UNSUPPORTED_PLATFORM_EXIT_CODE)
