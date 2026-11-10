"""Import-safe platform enforcement for mms_ok runtime entry points."""

import os
import sys

_UNSUPPORTED_PLATFORM_EXIT_CODE = 1
_UNSUPPORTED_PLATFORM_SIGNAL_ENV = "MMS_OK_UNSUPPORTED_PLATFORM_SIGNAL"
_UNSUPPORTED_PLATFORM_MESSAGE = (
    "mms_ok supports Windows and macOS; "
    "unsupported platform signal: {!r}."
)


def enforce_supported_runtime(critical=None) -> None:
    """Terminate early outside the supported desktop systems."""
    unsupported_signal = os.environ.get(_UNSUPPORTED_PLATFORM_SIGNAL_ENV)
    platform_signal = unsupported_signal or sys.platform
    if unsupported_signal is None and (os.name == "nt" or sys.platform == "darwin"):
        return

    message = _UNSUPPORTED_PLATFORM_MESSAGE.format(platform_signal)
    if critical is None:
        print("CRITICAL | {}".format(message), file=sys.stderr)
    else:
        critical(message)
    raise SystemExit(_UNSUPPORTED_PLATFORM_EXIT_CODE)


# Compatibility for callers of the former internal gate.
enforce_windows_runtime = enforce_supported_runtime
