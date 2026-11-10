# macOS FrontPanel 6.1.0 / XEM7310-A200 validation

Validated on 2026-11-10 (Asia/Seoul) from the local working tree.

## Environment

- macOS 27.0.1, arm64, 64-bit CPython 3.13.18.
- Project virtual environment: `.venv`, created with `python3.13 -m venv .venv`.
- Package and dependencies installed with `python -m pip install -e '.[test]'`.
- Official local wheel: `ok-6.1.0-cp311-abi3-macosx_10_15_universal2.whl`, supplied in the SDK's `API/Python` directory.
- Binding API `import ok`, version 6.1.0; wheel native extension `ok/_ok.abi3.so`.
- Board: XEM7310-A200; serial `224800128A`; product ID `44`.
- Board interface reports USB 3 capability; actual USB speed is **HIGH (High-Speed)**. Wire, Trigger, and Pipe widths are each 32 bits.
- Packaged bitstream: `mms_ok/bitstreams/A200_boardtest.bit`.
- Bitstream SHA-256: `f2381b26c330788b256ecd781d7d0ea38d0ca5a5df1c4ade20e9088cda54923c`.

The full environment, dependency versions, module paths, and reopen result are in [the environment log](frontpanel-6.1.0-macos-arm64-environment.txt).

## Hardware results

The commands below used `.venv/bin/python`. USB opening requires an execution environment with macOS USB access.

| Check | Result | Exit code |
| --- | --- | --- |
| `python -m mms_ok check-sdk` | FrontPanel 6.1.0 loaded from the installed official wheel | 0 |
| `python -m mms_ok doctor` | PASS; one device; no SDK folder or cache required | 0 |
| `python -m mms_ok devices` | XEM7310-A200, serial 224800128A | 0 |
| `python -m mms_ok bist --serial 224800128A` | All four functional test groups passed | 0 |
| Open the same serial after BIST, read identity, then close | PASS; same serial, model and product ID; closed successfully | 0 |

BIST ran at 12:56:11–12:56:17 KST using the packaged A200 bitstream:

| Test | Result |
| --- | --- |
| Wires | **32/32** |
| Pipes | **32/32** |
| BTPipes | **32/32** |
| Triggers | **32/32** |

See [the complete BIST output](frontpanel-6.1.0-macos-arm64-bist.txt). The process exited with code 0 and logged device closure. A separate process reopened the device at 12:56:50 KST and verified its identity before closing it.

The initial sandboxed `devices` attempt enumerated the serial but failed to open USB: `okCUsbDevice: Could not create plug-in (error -536870210)`. Running with USB access succeeded. The successful BIST and reopen checks used that same USB-capable execution environment.

## Loader checks

- Setting `MMS_OK_FRONTPANEL_DIR` to the local SDK root loaded `API/Python/ok.py`, reporting 6.1.0, ahead of the installed wheel.
- `setup-frontpanel --frontpanel-dir <sdk-root> --lib-dir /tmp/mms-ok-frontpanel-cache` copied `ok.py`, `_ok.so`, and `libokFrontPanel.2.dylib` successfully.
- With wheel discovery disabled for a cache-only probe, the copied native extension and Python binding loaded from `/tmp/mms-ok-frontpanel-cache`, reporting 6.1.0. The cache was complete.
- A real `doctor --frontpanel-dir <sdk-root> --lib-dir /tmp/mms-ok-frontpanel-cache` run passed with source `sdk`, the requested SDK binding/native paths, and one device. See [the doctor output](frontpanel-6.1.0-macos-arm64-doctor.txt).

## Automated validation

The initial, unmodified suite passed **239 tests**. The final suite covers the original Windows/FrontPanel 5 regression cases plus SDK 6 fakes without legacy discovery, product constants, error strings or endpoint methods; Classic port routing and ownership; identity validation and cleanup; macOS SDK/wheel/cache selection; path conflicts and restoration; missing libraries and incompatible Python/native environments; and CLI selection.

Run with:

```bash
.venv/bin/python -m pytest -q
```

Final result: **279 passed in 2.05s**. `git diff --check` also passed.

Both `mms_ok-2.3.0-py3-none-any.whl` and `mms_ok-2.3.0.tar.gz` built successfully. Their Python modules match the final working tree; each contains the three existing BIST bitstreams and the new compatibility module, with no vendor `ok.py`, `.so`, `.pyd`, `.dll`, `.dylib`, or wheel payload. The wheel retains `Requires-Python: >=3.7` and does not require installing `ok` merely to import the package or display help. All 25 package modules parse with Python 3.7 grammar. This syntax/metadata check is separate from the actual Python 3.13 hardware run.

See [the package audit output](frontpanel-6.1.0-macos-arm64-package.txt). The build emitted the repository's existing setuptools license-table deprecation warning; both artifacts built successfully.

## Limits

This is a functional test of this arm64 Mac, SDK 6.1.0 and A200 board over USB High-Speed. Other FrontPanel 6.x releases and Intel Macs have not been physically validated. Windows FrontPanel 5 compatibility is covered by regression fakes; a Windows hardware rerun was not performed here. USB 3.0 throughput and the Pythonic `frontpanel` API were outside scope.

BIST changed the volatile FPGA configuration. No firmware update or flash write was performed.
