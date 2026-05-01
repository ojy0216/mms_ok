# MMS-OK

`mms_ok` is a Python interface layer for Opal Kelly FPGA boards used in lab and hardware-control workflows. It wraps common FrontPanel operations—device configuration, wires, triggers, pipes, block pipes, register access, and built-in self-test (BIST)—behind a small Python API and a command-line entry point.

The package is intended for researchers and lab users who already have Opal Kelly hardware and bitstreams, and who want a repeatable way to install the Python package, check the FrontPanel SDK, run a board test, and script typical host-to-FPGA interactions.

## Supported boards

`mms_ok` currently provides board-specific classes for:

- `XEM7310` (`XEM7310A75` and `XEM7310A200`)
- `XEM7360` (`XEM7360K160T`)

The package also includes BIST bitstreams under `mms_ok/bitstreams` for supported board-test flows.

## What it provides

- Context-managed FPGA setup and cleanup.
- Bitstream loading through the Opal Kelly FrontPanel API.
- Wire-in and wire-out helpers.
- Trigger-in and trigger-out helpers.
- Pipe and block-pipe transfer helpers for strings, byte buffers, and NumPy arrays.
- Register bridge read/write helpers.
- LED helpers for supported XEM boards.
- CLI commands for version checks, SDK checks, FrontPanel setup, and BIST.

## Requirements

- **Windows only.**
  - `mms_ok` supports Windows environments only.
  - **macOS and Linux are not supported.**
- Python 3.7 or newer.
- An Opal Kelly board supported by this package.
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

Finally, verify that `mms_ok` can import the FrontPanel SDK as `ok`:

```bash
mms_ok check-sdk
```

If the SDK is installed but Python still cannot import `ok`, run the helper command and check again:

```bash
mms_ok setup-frontpanel
mms_ok check-sdk
```

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

## Typical lab workflow

A typical session is:

1. Install the Windows FrontPanel SDK with the setup guide above.
2. Install `mms_ok` and verify that it can import the FrontPanel SDK with `mms_ok check-sdk`.
3. Connect a supported XEM board and, when appropriate, verify it with `mms_ok bist`.
4. Load your `.bit` file with `XEM7310` or `XEM7360`.
5. Use wires, triggers, pipes, and registers to control and inspect your FPGA design.
6. Close the device when finished. Prefer a context manager in scripts.

### Script-style usage with a context manager

Use this pattern for normal Python scripts so the device is closed automatically:

```python
from mms_ok import XEM7310

BITSTREAM = "path/to/design.bit"

with XEM7310(BITSTREAM) as fpga:
    # Optional: reset the design through a wire endpoint.
    fpga.reset(reset_address=0x00, reset_time=1.0, active_low=True)

    # Control board LEDs. XEM7310 exposes 8 LEDs; XEM7360 exposes 4 LEDs.
    fpga.SetLED(0xFF)

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

```python
import numpy as np
from mms_ok import XEM7310

with XEM7310("path/to/design.bit") as fpga:
    # Write a hexadecimal payload to a pipe-in endpoint.
    written = fpga.WriteToPipeIn(0x80, "AABBCCDDEEFF0011")
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
from mms_ok import BIST, XEM7310, XEM7360
```

Common methods on `XEM7310` and `XEM7360` include:

- Device lifecycle: `close()`, context manager support, `reset(...)`.
- LEDs: `SetLED(...)`.
- Wires: `SetWireInValue(...)`, `UpdateWireIns()`, `UpdateWireOuts()`, `GetWireOutValue(...)`.
- Triggers: `ActivateTriggerIn(...)`, `UpdateTriggerOuts()`, `IsTriggered(...)`, `CheckTriggered(...)`.
- Pipes: `WriteToPipeIn(...)`, `ReadFromPipeOut(...)`, `WriteToBlockPipeIn(...)`, `ReadFromBlockPipeOut(...)`.
- Registers: `WriteRegister(...)`, `ReadRegister(...)`.

`ReadFromPipeOut` and `ReadFromBlockPipeOut` return a `PipeOutData` object with `error_code`, `transfer_byte`, `raw_data`, `hex_data`, and `to_ndarray(dtype)`.

## Contact

For questions, bug reports, or feature requests, contact:

`juyoung.oh@snu.ac.kr`
