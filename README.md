# MMS-OK: FPGA Interface Library

A Python library for interfacing with FPGA devices using the Opal Kelly FrontPanel API. This library provides a high-level interface for wire, trigger, and pipe operations with FPGA devices.

## Features

- Wire-based I/O operations (setting/getting wire values)
- Trigger-based operations (activating triggers, checking trigger states)
- Pipe data transfer operations (reading/writing data through pipes)
- Block pipe operations for efficient large data transfers
- Comprehensive error handling and validation
- Utilities for data conversion and manipulation
- Support for XEM7310 and XEM7360 FPGA boards
- Register bridge operations (reading/writing registers)
- Automatic update control for wire and trigger operations
- Context manager support for safe device handling

## Installation

### Prerequisites

- Python 3.7 or higher
- NumPy
- BitSlice
- Loguru
- Rich
- Opal Kelly FrontPanel API
- Install the Opal Kelly FrontPanel API according to the [official documentation](https://docs.opalkelly.com/fpsdk/frontpanel-api/).

### Install Guide
```bash
pip install mms_ok
```

## Quick Start

### Using the XEM Classes

```python
from mms_ok import XEM7310, XEM7360

# For XEM7310 boards
with XEM7310("path/to/bitstream.bit") as fpga:
    # Reset the FPGA
    fpga.reset(reset_address=0x00, reset_time=1.0, active_low=True)
    
    # Control LEDs (8 LEDs on XEM7310)
    fpga.SetLED(led_value=0xFF)  # Turn on all LEDs
    
    # Set wire values
    fpga.SetWireInValue(0x00, 0x12345678)
    fpga.UpdateWireIns()
    
    # Read wire values
    value = fpga.GetWireOutValue(0x20, auto_update=True)
    print(f"Wire value: 0x{value:08X}")
    
    # Activate a trigger
    fpga.ActivateTriggerIn(0x40, 0)
    
    # Check if a trigger is set
    if fpga.IsTriggered(0x60, 0x01, auto_update=True):
        print("Trigger is set!")
    
    # Wait for a trigger with timeout
    try:
        fpga.CheckTriggered(0x60, 0x01, timeout=2.0)
        print("Trigger condition met!")
    except TimeoutError:
        print("Trigger timeout!")
    
    # Read data from a pipe
    data = fpga.ReadFromPipeOut(0xA0, 1024, reorder_str=True)
    print(f"Received data: {data.hex_data}")
    print(f"Error code: {data.error_code}")
    
    # Convert data to numpy array
    import numpy as np
    array_data = data.to_ndarray(dtype=np.uint16)
    print(f"As array: {array_data}")

# For XEM7360 boards
fpga = XEM7360("path/to/bitstream.bit"):

# XEM7360 has 4 LEDs
fpga.SetLED(led_value=0x0F)  # Turn on all 4 LEDs

# The rest of the API is the same as XEM7310

fpga.close()
```

### Automatic Updates

```python
from mms_ok import XEM7310

with XEM7310("path/to/bitstream.bit") as fpga:
    # Enable automatic updates
    fpga.SetAutoWireIn(True)
    fpga.SetAutoWireOut(True)
    fpga.SetAutoTriggerOut(True)
    
    # Now you don't need to call update methods explicitly
    fpga.SetWireInValue(0x00, 0x12345678)  # Auto-updates
    value = fpga.GetWireOutValue(0x20)     # Auto-updates before reading
    is_triggered = fpga.IsTriggered(0x60, 0x01)  # Auto-updates before checking
    
    # Disable automatic updates when needed
    fpga.SetAutoWireIn(False)
    fpga.SetAutoWireOut(False)
    fpga.SetAutoTriggerOut(False)
    
    # Now you need to call update methods explicitly
    fpga.SetWireInValue(0x01, 0xABCDEF01)
    fpga.SetWireInValue(0x02, 0x12345678)
    fpga.UpdateWireIns()  # Updates all wire-in values at once
    
    fpga.UpdateWireOuts()  # Explicitly update before reading
    value = fpga.GetWireOutValue(0x21)
    
    # You can also use auto_update parameter for one-time automatic updates
    # without changing the global setting
    fpga.SetWireInValue(0x03, 0x55AA55AA, auto_update=True)  # One-time auto-update
    value = fpga.GetWireOutValue(0x22, auto_update=True)     # One-time auto-update
```

### Reading and Writing Data

```python
from mms_ok import XEM7310
import numpy as np

with XEM7310("path/to/bitstream.bit") as fpga:
    # Write data to a pipe
    # You can write string data (hex format)
    fpga.WriteToPipeIn(0x80, "AABBCCDDEEFF0011", reorder_str=True)
    
    # Or numpy arrays
    data_array = np.array([1, 2, 3, 4], dtype=np.uint32)
    fpga.WriteToPipeIn(0x80, data_array)
    
    # Or raw bytearrays
    raw_data = bytearray([0xAA, 0xBB, 0xCC, 0xDD] * 4)
    fpga.WriteToPipeIn(0x80, raw_data)
    
    # Read data from a pipe
    # Specify buffer size in bytes
    result = fpga.ReadFromPipeOut(0xA0, 16)
    print(f"Hex data: {result.hex_data}")
    print(f"Raw data: {result.raw_data}")
    
    # For larger transfers, use block pipes
    large_data = np.zeros(1024, dtype=np.uint32)
    fpga.WriteToBlockPipeIn(0x80, large_data)
    
    # Read large data blocks
    large_result = fpga.ReadFromBlockPipeOut(0xA0, 4096)  # 4096 bytes
```

### Register Operations

```python
from mms_ok import XEM7310

with XEM7310("path/to/bitstream.bit") as fpga:
    # Write to a register
    fpga.WriteRegister(0x1000, 0x12345678)
    
    # Read from a register
    value = fpga.ReadRegister(0x1000)
    print(f"Register value: 0x{value:08X}")
```

## API Documentation

### XEM Base Class

Abstract base class for Opal Kelly FPGA devices. Provides common functionality for all FPGA models.

#### Methods

- `reset(reset_address, reset_time, active_low)`: Reset the FPGA device
- `SetLED(led_value, led_address)`: Set LED values on the FPGA board
- `SetAutoWireIn(auto_update)`: Enable automatic update of wire-in values
- `SetAutoWireOut(auto_update)`: Enable automatic update of wire-out values
- `SetAutoTriggerOut(auto_update)`: Enable automatic update of trigger-out values
- `SetWireInValue(ep_addr, value, mask, auto_update)`: Set a value to be written to a wire-in endpoint
- `UpdateWireIns()`: Update all wire-in endpoints
- `UpdateWireOuts()`: Update all wire-out endpoints
- `GetWireOutValue(ep_addr, auto_update)`: Get the value of a wire-out endpoint
- `WriteToPipeIn(ep_addr, data, reorder_str)`: Write data to a pipe-in endpoint
- `ReadFromPipeOut(ep_addr, data, reorder_str)`: Read data from a pipe-out endpoint
- `WriteToBlockPipeIn(ep_addr, data, block_size, reorder_str)`: Write data to a block pipe-in endpoint
- `ReadFromBlockPipeOut(ep_addr, data, block_size, reorder_str)`: Read data from a block pipe-out endpoint
- `ActivateTriggerIn(ep_addr, bit)`: Activate a trigger-in endpoint
- `UpdateTriggerOuts()`: Update all trigger-out endpoints
- `IsTriggered(ep_addr, mask, auto_update)`: Check if specific trigger bits are set
- `CheckTriggered(ep_addr, mask, timeout)`: Check if a trigger condition is met within a specified timeout
- `WriteRegister(addr, data)`: Write a value to a register bridge
- `ReadRegister(addr)`: Read a value from a register bridge

### XEM7310 Class

Specific implementation for the XEM7310A75/A200 FPGA boards. Inherits from XEM base class.

#### Methods

All methods from XEM base class, plus:
- `SetLED(led_value, led_address)`: Control the 8 LEDs on the XEM7310 board

### XEM7360 Class

Specific implementation for the XEM7360K160T FPGA board. Inherits from XEM base class.

#### Methods

All methods from XEM base class, plus:
- `SetLED(led_value, led_address)`: Control the 4 LEDs on the XEM7360 board

### PipeOutData

Represents data received from a pipe out interface.

#### Properties

- `error_code`: The error code associated with the data
- `raw_data`: The raw binary data received
- `hex_data`: Hexadecimal string representation of the data
- `transfer_byte`: The number of bytes transferred

#### Methods

- `to_ndarray(dtype)`: Convert the data to a numpy array with the specified dtype

## Endpoint Address Ranges

- Wire-in endpoints: `0x00 - 0x1F`
- Wire-out endpoints: `0x20 - 0x3F`
- Trigger-in endpoints: `0x40 - 0x5F`
- Trigger-out endpoints: `0x60 - 0x7F`
- Pipe-in endpoints: `0x80 - 0x9F`
- Pipe-out endpoints: `0xA0 - 0xBF`

# Contact
For questions, bug reports, or feature requests, please contact:

juyoung.oh@snu.ac.kr
