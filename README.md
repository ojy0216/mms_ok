# MMS-OK

`mms_ok` is a Python interface layer for Opal Kelly FPGA boards used in lab and hardware-control workflows. It wraps common FrontPanel operations—device configuration, wires, triggers, pipes, block pipes, register access, and built-in self-test (BIST)—behind a small Python API and a command-line entry point.

The package is intended for researchers and lab users who already have Opal Kelly hardware and bitstreams, and who want a repeatable way to install the Python package, check the FrontPanel SDK, run a board test, and script typical host-to-FPGA interactions.

## Supported boards

`mms_ok` currently provides board-specific classes for:

- `XEM7310` (`XEM7310A75` and `XEM7310A200`)
- `XEM7360` (`XEM7360K160T`)

The package also includes BIST bitstreams under `mms_ok/bitstreams` for supported board-test flows.
`XEM(...)` can open other attached Opal Kelly boards for best-effort common
FrontPanel API access, but unknown boards are not hardware-verified by `mms_ok`
and do not get board-specific LED behavior or BIST support.

## What it provides

- Context-managed FPGA setup and cleanup.
- Bitstream loading through the Opal Kelly FrontPanel API.
- Wire-in and wire-out helpers.
- Trigger-in and trigger-out helpers.
- Pipe and block-pipe transfer helpers for strings, byte buffers, and NumPy arrays.
- Register bridge read/write helpers.
- LED helpers for supported XEM boards.
- Device discovery from Python and the CLI.
- CLI commands for version checks, SDK checks, FrontPanel setup, device listing, and BIST.

## Requirements

- **Windows only.**
  - `mms_ok` supports Windows environments only.
  - **macOS and Linux are not supported.**
- Python 3.7 or newer.
- An Opal Kelly board. XEM7310/XEM7360 boards are hardware-verified by this
  package; other Opal Kelly boards are best-effort for common FrontPanel APIs.
- The Opal Kelly FrontPanel SDK for Windows. FrontPanel SDK `5.3.6` is recommended.
- Python dependencies installed by `pip`: `numpy`, `bitslice`, `loguru`, `rich`, and `tqdm`.

`mms_ok` imports the FrontPanel Python module as `ok`. When the Windows SDK is installed in the default Opal Kelly location, `mms_ok setup-frontpanel` can copy the default FrontPanel Python files into the user's Windows home directory, such as `%USERPROFILE%\mms_ok`.

## FrontPanel SDK setup on Windows

Install the Opal Kelly FrontPanel SDK before installing `mms_ok`, so the SDK files and Windows driver are already present when `mms_ok` verifies the environment.

1. Go to the [Opal Kelly downloads page](https://pins.opalkelly.com/downloads) and sign in with an authorized Opal Kelly account.
2. Open **File Downloads**.
3. Download the Windows x64 installer for the recommended SDK version. The expected filename is:

   ```text
   FrontPanelUSB-Win-x64-5.3.6.exe
   ```

4. Run the installer and keep the default install location unless your lab setup requires otherwise.

## Installation

After the FrontPanel SDK is installed, install `mms_ok` from PyPI:

```bash
pip install mms_ok
```

Then check that the command-line entry point is available:

```bash
mms_ok --help
mms_ok version
```

Running `mms_ok` with no arguments opens an arrow-key setup helper menu for
common FrontPanel and Jupyter environment diagnostics.

Finally, verify that `mms_ok` can import the FrontPanel SDK as `ok`:

```bash
mms_ok check-sdk
```

If the SDK is installed but Python still cannot import `ok`, run the helper command and check again:

```bash
mms_ok setup-frontpanel
mms_ok check-sdk
```

## Device discovery and autodetect

List attached FrontPanel devices from the CLI:

```bash
mms_ok devices
python -m mms_ok devices
```

The command prints `device_id`, `model`, and `serial`.
`device_id` is the Opal Kelly `okTDeviceInfo.deviceID` string.

Use the same discovery from Python:

```python
import mms_ok

for device in mms_ok.list_devices():
    print(device.serial, device.model, device.device_id, device.product_id)
```

`mms_ok.list_devices()` imports the FrontPanel SDK lazily, so `import mms_ok`
does not require the SDK to be installed.

Use `XEM(...)` when you want `mms_ok` to choose the concrete FPGA class
from the connected board:

```python
from mms_ok import XEM

with XEM("path/to/design.bit") as fpga:
    print(type(fpga).__name__)
```

Autodetect behavior:

- Exactly one attached XEM7310-A75/A200 opens as `XEM7310`.
- Exactly one attached XEM7360-K160T opens as `XEM7360`.
- Other Opal Kelly product IDs open as a generic unverified device for
  best-effort common FrontPanel APIs.
- Zero attached devices raises `FPGASelectionError`.
- More than one attached device requires `serial=...` and raises
  `FPGASelectionError` if omitted.
- A provided `serial` must match a discovered device, otherwise
  `FPGASelectionError` is raised.
- If the selected device changes serial or exact product ID between discovery
  and the constructor reopen, `ProductIDMismatchError` is raised before
  `ConfigureFPGA` is called.

`XEM` is public at the top level:

```python
from mms_ok import XEM
```

Advanced users can import facade details and the shared base class from
`mms_ok.fpga`. For legacy compatibility, `mms_ok.fpga.XEM` remains the base
class; the facade exposes the autodetect factory as `autodetect_xem`.

```python
from mms_ok.fpga import FPGASelectionError, ProductIDMismatchError, UnverifiedXEM, XEM, XEMBase, autodetect_xem
```

`UnverifiedXEM` is facade-visible for introspection and tests, but it is not a
top-level public constructor promise. Prefer top-level `mms_ok.XEM(...)` for
normal autodetect usage.

## Built-in self-test (BIST)

BIST is the quickest way to confirm that the installed package, FrontPanel SDK, connected board, and packaged board-test bitstream can work together.

Run it from the CLI:

```bash
mms_ok bist
```

Equivalent module execution:

```bash
python -m mms_ok bist
```

The package first looks for its packaged BIST bitstreams. For backward compatibility, it can also fall back to `%USERPROFILE%\mms_ok\bitstreams` if packaged files are unavailable.

## Bitstream paths

`XEM(bitstream_path)`, `XEM7310(bitstream_path)`, and
`XEM7360(bitstream_path)` accept absolute paths, such as
`C:\path\to\design.bit`. `~` and environment variables are expanded. When only
a bitstream filename such as `design.bit` is provided, it is loaded from
`../bitstreams` relative to the current working directory.

Examples:

```python
from mms_ok import XEM7310

# Absolute path: uses this exact file after path expansion.
fpga = XEM7310(r"C:\Users\JY\fpga\design.bit")

# User-home path: "~" expands to the current user's home directory.
fpga = XEM7310("~/fpga/design.bit")

# Environment variable path: "%USERPROFILE%" expands before loading.
fpga = XEM7310(r"%USERPROFILE%\fpga\design.bit")

# Filename only: loads "../bitstreams/design.bit" from the current working directory.
fpga = XEM7310("design.bit")
```

If a bitstream is missing, the error message includes the checked candidate
paths. BIST continues to use the packaged bitstreams under `mms_ok/bitstreams`
first, then the legacy `%USERPROFILE%\mms_ok\bitstreams` fallback.

## Typical lab workflow

A typical session is:

1. Install the Windows FrontPanel SDK with the setup guide above.
2. Install `mms_ok` and verify that it can import the FrontPanel SDK with `mms_ok check-sdk`.
3. Connect an Opal Kelly board and verify visibility with `mms_ok devices`.
4. When appropriate, verify the board with `mms_ok bist`.
5. Load your `.bit` file with `XEM`, `XEM7310`, or `XEM7360`.
6. Use wires, triggers, pipes, and registers to control and inspect your FPGA design.
7. Close the device when finished. Prefer a context manager in scripts.

### Script-style usage with a context manager

Use this pattern for normal Python scripts so the device is closed automatically:

```python
from mms_ok import XEM

BITSTREAM = "path/to/design.bit"

with XEM(BITSTREAM) as fpga:
    # Optional: reset the design through a wire endpoint.
    fpga.reset(reset_address=0x00, reset_time=1.0, active_low=True)

    # Optional board-specific LED control. Generic unverified boards raise
    # NotImplementedError because their LED wiring is not hardware-validated.
    try:
        fpga.SetLED(0xFF)
    except NotImplementedError:
        pass

    # Write control words through wire-in endpoints.
    fpga.SetWireInValue(0x00, 0x12345678)
    fpga.SetWireInValue(0x01, 0x00000001)

    # Read status through a wire-out endpoint.
    status = fpga.GetWireOutValue(0x20)
    print(f"status = 0x{status:08X}")

    # Start an operation with a trigger-in endpoint.
    fpga.ActivateTriggerIn(0x40, 0)

    # Wait for a trigger-out completion flag.
    fpga.CheckTriggered(0x60, 0x01, timeout=2.0)
```

`XEM(...)` autodetects the single attached FrontPanel device and returns
`XEM7310`, `XEM7360`, or a generic unverified device for other Opal Kelly
product IDs. If more than one device is attached, pass a serial number from
`mms_ok devices` or `mms_ok.list_devices()`:

```python
from mms_ok import XEM

with XEM("path/to/design.bit", serial="SERIAL123") as fpga:
    fpga.SetWireInValue(0x00, 0x00000001)
```

The board-specific constructors also accept `serial` as a keyword-only argument
when you want to require a verified board family and target a specific device:

```python
from mms_ok import XEM7310

with XEM7310("path/to/design.bit", serial="SERIAL123") as fpga:
    fpga.SetLED(0xFF)
```

Passing the serial positionally is intentionally not supported; use
`serial="..."`.

You can still use strict verified constructors directly when you want to require
a specific board family. These constructors reject the wrong connected product
before configuring the FPGA:

```python
from mms_ok import XEM7310, XEM7360

with XEM7310("path/to/design.bit") as fpga:
    fpga.SetLED(0xFF)

with XEM7360("path/to/design.bit") as fpga:
    fpga.SetLED(0x0F)
```

Generic unverified boards returned by `XEM(...)` emit a runtime warning.
They inherit common wires, triggers, pipes, block pipes, registers, reset, and
lifecycle methods, but board-specific helpers such as `SetLED(...)` are not
supported and BIST remains limited to the verified boards listed above.

### Notebook or interactive usage

In notebooks, it is often convenient to keep the object open across cells. Close it explicitly when you are done:

```python
from mms_ok import XEM7360

fpga = XEM7360("path/to/design.bit")

# Run interactive experiments here.
fpga.SetWireInValue(0x00, 0x00000001)
value = fpga.GetWireOutValue(0x20)
print(value)

fpga.close()
```

## Common API examples

### Automatic and manual updates

Wire and trigger output reads are automatically updated by default. You can disable automatic updates when you want to batch operations manually:

```python
from mms_ok import XEM7310

with XEM7310("path/to/design.bit") as fpga:
    fpga.SetAutoWireIn(False)
    fpga.SetWireInValue(0x00, 0x11111111)
    fpga.SetWireInValue(0x01, 0x22222222)
    fpga.UpdateWireIns()

    fpga.SetAutoWireOut(False)
    fpga.UpdateWireOuts()
    result = fpga.GetWireOutValue(0x20)

    # One call can still request an update explicitly.
    latest = fpga.GetWireOutValue(0x21, auto_update=True)
```

### Pipe transfers

Use pipe endpoints for host-to-FPGA and FPGA-to-host data movement. Strings, `bytearray` objects, and NumPy arrays are accepted for writes.
Hexadecimal strings are interpreted as FPGA words using `endian="little"` by default. Pass `endian="big"` to preserve the original hex byte order.

```python
import numpy as np
from mms_ok import XEM7310

with XEM7310("path/to/design.bit") as fpga:
    # Write a hexadecimal payload to a pipe-in endpoint.
    written = fpga.WriteToPipeIn(0x80, "AABBCCDDEEFF00112233445566778899")
    print(f"wrote {written} bytes")

    # Write a NumPy array.
    samples = np.array([1, 2, 3, 4], dtype=np.uint32)
    fpga.WriteToPipeIn(0x80, samples)

    # Read 16 bytes from a pipe-out endpoint.
    packet = fpga.ReadFromPipeOut(0xA0, 16)
    print(packet.hex_data)
    print(packet.raw_data)

    # Convert received bytes to a typed NumPy view.
    words = packet.to_ndarray(dtype=np.uint32)
    print(words)
```

#### Pipe transaction details

A pipe transaction is one explicit buffer transfer between the host program and a
FrontPanel pipe endpoint:

- `WriteToPipeIn(0x80, data, ...)` sends one prepared byte buffer from the host
  to a pipe-in endpoint in the `0x80`-`0x9F` range.
- `ReadFromPipeOut(0xA0, size_or_buffer, ...)` fills a host buffer from a
  pipe-out endpoint in the `0xA0`-`0xBF` range.
- Normal pipe transfers must be a multiple of 16 bytes. For reads, pass either
  an integer byte count, such as `16`, or an existing `bytearray` buffer.
- Successful reads return `PipeOutData`. Use `raw_data` for the exact bytes from
  the FPGA, `hex_data` for word-formatted hexadecimal text, and
  `to_ndarray(dtype)` for a NumPy view over the raw bytes.
- Negative FrontPanel return codes are raised as `RuntimeError`.

For write calls, each supported input type is prepared differently:

| Input type | Pipe behavior |
| --- | --- |
| Hex string | Parsed as FPGA words and converted to bytes using `endian`. Whitespace accepted by `bytearray.fromhex` is allowed. |
| `bytearray` | Sent exactly as provided. `endian` and `reverse` do not rewrite raw byte buffers. |
| NumPy integer array | Flattened in C order, then each element is encoded using `endian`, independent of the array dtype byte order. |
| NumPy non-integer array | Flattened in C order and sent as contiguous raw bytes. |

#### `endian` and `reverse`

`endian` controls byte order inside each formatted word. For normal pipes, hex
strings and `PipeOutData.hex_data` use 32-bit words:

```python
# Four 32-bit words: AABBCCDD 11223344 55667788 9900A1B2
payload = "AABBCCDD11223344556677889900A1B2"

# Default: endian="little"; each 32-bit word is byte-swapped on the wire.
fpga.WriteToPipeIn(0x80, payload)
# bytes sent: DD CC BB AA  44 33 22 11  88 77 66 55  B2 A1 00 99

# Big endian preserves the hex byte order inside each word.
fpga.WriteToPipeIn(0x80, payload, endian="big")
# bytes sent: AA BB CC DD  11 22 33 44  55 66 77 88  99 00 A1 B2
```

The same option affects the display format for reads. If the FPGA returns raw
bytes `DD CC BB AA`, `ReadFromPipeOut(..., endian="little").hex_data` is
`"AABBCCDD"`, while `endian="big"` reports `"DDCCBBAA"`. `raw_data` is never
changed by formatting options.

`reverse=True` reverses transfer/display order at the word or element level:

- Hex-string writes reverse the order of 32-bit words before applying `endian`.
- NumPy writes reverse flattened array elements before byte conversion.
- Pipe reads reverse the order of 32-bit words in `hex_data` only; `raw_data`
  remains in the exact order received from FrontPanel.
- `bytearray` writes are treated as already-final raw bytes, so `reverse=True`
  leaves them unchanged.

Example with the payload above:

```python
fpga.WriteToPipeIn(0x80, payload, reverse=True)
# logical word order becomes: 9900A1B2 55667788 11223344 AABBCCDD
# default little-endian bytes sent:
# B2 A1 00 99  88 77 66 55  44 33 22 11  DD CC BB AA

packet = fpga.ReadFromPipeOut(0xA0, 16, reverse=True)
print(packet.raw_data)  # unchanged raw bytes
print(packet.hex_data)  # 32-bit words displayed latest-word first
```

`reorder_str` is still accepted for older code, but it is deprecated. Prefer
`endian="little"` for the old reordered-word behavior or `endian="big"` when
the original hex byte order should be preserved.

### Block pipe transfers

Use block pipes for larger transfers when your FPGA design exposes block pipe endpoints:

```python
import numpy as np
from mms_ok import XEM7310

with XEM7310("path/to/design.bit") as fpga:
    payload = np.arange(1024, dtype=np.uint32)
    fpga.WriteToBlockPipeIn(0x80, payload)

    received = fpga.ReadFromBlockPipeOut(0xA0, 4096)
    data = received.to_ndarray(dtype=np.uint32)
```

Block pipe write and read helpers accept the same `endian` and `reverse`
options. The difference is transfer sizing: block pipes use a `block_size`
selected from the connected transport when omitted, and the total transfer byte
count must be compatible with that block size. For hex strings, USB 2 block
pipes format 16-bit words; USB 3, PCIe, and the default policy format 32-bit
words. `reverse=True` still reverses 32-bit groups for hex-string writes and
`hex_data` display.

### Register bridge operations

If your bitstream exposes a FrontPanel register bridge, use `WriteRegister` and `ReadRegister` with 32-bit register addresses and values:

```python
from mms_ok import XEM7310

with XEM7310("path/to/design.bit") as fpga:
    fpga.WriteRegister(0x1000, 0x12345678)
    value = fpga.ReadRegister(0x1000)
    print(f"register = 0x{value:08X}")
```

## Endpoint address ranges

FrontPanel endpoint ranges used by the helpers follow the standard Opal Kelly layout:

| Endpoint type | Address range |
| --- | --- |
| Wire in | `0x00`–`0x1F` |
| Wire out | `0x20`–`0x3F` |
| Trigger in | `0x40`–`0x5F` |
| Trigger out | `0x60`–`0x7F` |
| Pipe in | `0x80`–`0x9F` |
| Pipe out | `0xA0`–`0xBF` |

## API surface at a glance

Import the public classes from `mms_ok`:

```python
from mms_ok import BIST, XEM, XEM7310, XEM7360, list_devices
```

Facade-only FPGA helpers and the shared base class are available from
`mms_ok.fpga`. For compatibility, `mms_ok.fpga.XEM` is the shared base class;
use top-level `mms_ok.XEM(...)` or facade `autodetect_xem(...)` for
autodetect construction:

```python
from mms_ok.fpga import FPGASelectionError, ProductIDMismatchError, UnverifiedXEM, XEM, XEMBase, autodetect_xem
```

Common methods on `XEM7310`, `XEM7360`, and generic devices returned by
`XEM(...)` include:

- Discovery: `list_devices()`, `XEM(...)`.
- Device lifecycle: `close()`, context manager support, `reset(...)`.
- LEDs: `SetLED(...)` on verified XEM7310/XEM7360 only.
- Wires: `SetWireInValue(...)`, `UpdateWireIns()`, `UpdateWireOuts()`, `GetWireOutValue(...)`.
- Triggers: `ActivateTriggerIn(...)`, `UpdateTriggerOuts()`, `IsTriggered(...)`, `CheckTriggered(...)`.
- Pipes: `WriteToPipeIn(...)`, `ReadFromPipeOut(...)`, `WriteToBlockPipeIn(...)`, `ReadFromBlockPipeOut(...)`.
- Registers: `WriteRegister(...)`, `ReadRegister(...)`.

On success, `ReadFromPipeOut` and `ReadFromBlockPipeOut` return a `PipeOutData`
object with `error_code`, `transfer_byte`, `raw_data`, `hex_data`, and
`to_ndarray(dtype)`. Negative Opal Kelly return codes raise `RuntimeError`
instead of returning `PipeOutData(error_code=<negative>)`.

## Contact

For questions, bug reports, or feature requests, contact:

`juyoung.oh@snu.ac.kr`
