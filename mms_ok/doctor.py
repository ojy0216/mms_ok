"""FrontPanel diagnostics command implementation."""

from __future__ import annotations

import os

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .ok_setup import (
    frontpanel_cache_status,
    get_frontpanel_version,
    probe_frontpanel_import,
    python_bitness,
    resolve_path,
)


STATUS_PASS = "[O]"
STATUS_FAIL = "[X]"
STATUS_WARN = "[!]"
STATUS_STYLES = {
    STATUS_PASS: "green",
    STATUS_FAIL: "red",
    STATUS_WARN: "yellow",
}
CRITICAL_CHECKS = {
    "SDK path",
    "Python bitness",
    "_ok native module",
    "ok import",
    "FrontPanel API",
    "Device count",
}
LVS_SMILE_ART = r"""
          #    ##############      _   _
         #     #            #      *   *
    #   #      #    PASS    #        |
     # #       #            #      \___/
      #        ##############
"""
LVS_X_ART = r"""
    #   #      ##############      _   _
     # #       #            #      *   *
      #        #    FAIL    #        |
     # #       #            #       ___
    #   #      ##############      /   \
"""


def _get_device_count(ok_module):
    try:
        frontpanel = ok_module.okCFrontPanel()
        return frontpanel.GetDeviceCount(), None
    except Exception as exc:
        return None, "{}: {}".format(type(exc).__name__, exc)


def _add_doctor_row(table, status, check, result, details=""):
    table.add_row(Text(status, style=STATUS_STYLES[status]), check, result, details)


def _append_doctor_row(rows, status, check, result, details=""):
    rows.append((status, check, result, details))


def run_doctor(frontpanel_dir: str, lib_dir: str) -> int:
    frontpanel_dir = resolve_path(frontpanel_dir)
    lib_dir = resolve_path(lib_dir)
    cache = frontpanel_cache_status(lib_dir)
    probe = probe_frontpanel_import(lib_dir)
    ok_module = probe["ok_module"]
    sdk_exists = os.path.isdir(frontpanel_dir)
    pyd_present = cache["files"]["_ok.pyd"]["exists"]

    api_version = "unavailable"
    device_count = "unavailable"
    device_error = None
    device_status = STATUS_FAIL
    if ok_module is not None:
        api_version = get_frontpanel_version(ok_module)
        device_count, device_error = _get_device_count(ok_module)
        if device_count is None:
            device_count = "unavailable"
        elif device_count == 0:
            device_status = STATUS_WARN
        else:
            device_status = STATUS_PASS

    table = Table(title="FrontPanel Diagnostics", show_header=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Result")
    table.add_column("Details", overflow="fold")

    cache_state = "complete"
    if cache["partial"]:
        cache_state = "partial"
    elif cache["missing"]:
        cache_state = "missing"

    rows = []
    _append_doctor_row(
        rows,
        STATUS_PASS if sdk_exists else STATUS_FAIL,
        "SDK path",
        "found" if sdk_exists else "missing",
        frontpanel_dir,
    )
    cache_status = STATUS_PASS
    if cache["partial"] or cache["missing"]:
        cache_status = STATUS_WARN
    _append_doctor_row(rows, cache_status, "Local cache", cache_state, cache["path"])
    for filename, info in cache["files"].items():
        _append_doctor_row(
            rows,
            STATUS_PASS if info["exists"] else STATUS_WARN,
            "Cache file",
            "present" if info["exists"] else "missing",
            "{}: {}".format(filename, info["path"]),
        )
    bitness = python_bitness()
    _append_doctor_row(
        rows,
        STATUS_PASS if bitness == 64 else STATUS_FAIL,
        "Python bitness",
        "{}-bit".format(bitness),
        "x64 FrontPanel files require 64-bit Python",
    )
    _append_doctor_row(
        rows,
        STATUS_PASS if probe["_ok_imported"] else STATUS_FAIL,
        "_ok native module",
        "imported"
        if probe["_ok_imported"]
        else "present/import failed"
        if pyd_present
        else "not importable",
        probe["_ok_error"] or cache["files"]["_ok.pyd"]["path"],
    )
    _append_doctor_row(
        rows,
        STATUS_PASS if probe["ok_imported"] else STATUS_FAIL,
        "ok import",
        "imported" if probe["ok_imported"] else "failed",
        probe["ok_error"] or ("used local cache" if probe["used_cache_path"] else ""),
    )
    _append_doctor_row(
        rows,
        STATUS_PASS if ok_module is not None else STATUS_FAIL,
        "FrontPanel API",
        str(api_version),
        "",
    )
    _append_doctor_row(
        rows,
        device_status,
        "Device count",
        str(device_count),
        device_error or "queried via ok.okCFrontPanel",
    )
    for row in rows:
        _add_doctor_row(table, *row)

    guidance = []
    if not sdk_exists:
        guidance.append(
            "FrontPanel SDK path is missing. Install the Opal Kelly FrontPanel SDK "
            "or pass --frontpanel-dir to the installed SDK path."
        )
    if cache["partial"] or cache["missing"]:
        guidance.append(
            "Optional local cache is not complete. If imports rely on the cache, "
            "run `mms_ok reset-cache` after confirming the SDK path is correct."
        )
    if not probe["ok_imported"]:
        guidance.append(
            "The ok module could not be imported. Use 64-bit Python with the x64 "
            "FrontPanel files, refresh the cache, and ensure ok/_ok.pyd is not locked."
        )
    if pyd_present and not probe["_ok_imported"]:
        guidance.append(
            "_ok.pyd exists but did not import directly. This usually indicates a DLL "
            "load/path mismatch or a Python bitness mismatch."
        )
    if probe["ok_imported"] and device_error is not None:
        guidance.append(
            "The ok module imported, but FrontPanel API probing failed: {}. Check "
            "for an unrelated ok package earlier on sys.path or a broken FrontPanel "
            "runtime.".format(device_error)
        )
    if not guidance:
        guidance.append("No critical FrontPanel setup issue detected.")

    console = Console()
    console.print(table)
    console.print("\nActionable guidance:")
    for item in guidance:
        console.print("- {}".format(item))

    critical_failure = any(
        status == STATUS_FAIL and check in CRITICAL_CHECKS
        for status, check, _result, _details in rows
    )
    console.print(LVS_X_ART if critical_failure else LVS_SMILE_ART)
    return 1 if critical_failure else 0
