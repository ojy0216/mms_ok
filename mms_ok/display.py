"""Console display helpers for mms_ok."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable, Tuple

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console(stderr=True, highlight=False)
PANEL_BORDER_STYLE = "grey50"
PANEL_TITLE_STYLE = "bold white"
MMS_OK_LOGO = r"""
███╗   ███╗███╗   ███╗███████╗     ██████╗ ██╗  ██╗
████╗ ████║████╗ ████║██╔════╝    ██╔═══██╗██║ ██╔╝
██╔████╔██║██╔████╔██║███████╗    ██║   ██║█████╔╝
██║╚██╔╝██║██║╚██╔╝██║╚════██║    ██║   ██║██╔═██╗
██║ ╚═╝ ██║██║ ╚═╝ ██║███████║    ╚██████╔╝██║  ██╗
╚═╝     ╚═╝╚═╝     ╚═╝╚══════╝     ╚═════╝ ╚═╝  ╚═╝"""

# MMS_OK_LOGO = r"""
# ███    ███ ███    ███ ███████      ██████  ██   ██ 
# ████  ████ ████  ████ ██          ██    ██ ██  ██  
# ██ ████ ██ ██ ████ ██ ███████     ██    ██ █████   
# ██  ██  ██ ██  ██  ██      ██     ██    ██ ██  ██  
# ██      ██ ██      ██ ███████      ██████  ██   ██ """


def _kv_table(rows: Iterable[Tuple[str, object]]) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", no_wrap=True, justify="left")
    table.add_column(ratio=1, overflow="fold", justify="left")

    for key, value in rows:
        table.add_row(key, value)

    return table


def _make_panel(title: str, body, border_style: str = "cyan") -> Panel:
    title_text = Text(title, style=PANEL_TITLE_STYLE) if title else ""
    return Panel(
        body,
        title=title_text,
        title_align="left",
        border_style=PANEL_BORDER_STYLE,
        box=box.ROUNDED,
        padding=(0, 2),
    )


def _panel(title: str, body, border_style: str = "cyan") -> None:
    console.print(_make_panel(title, body, border_style))


def _version_label(version: str) -> str:
    if not version or version == "unknown":
        return "unknown"
    return version if version.startswith("v") else f"v{version}"


def _header_panel(version: str, frontpanel_version: str) -> Table:
    header = Table.grid(expand=True, padding=(0, 4))
    header.add_column(no_wrap=True)
    header.add_column(ratio=1, justify="left")

    version_table = Table.grid(padding=(0, 2))
    version_table.add_column(style="dim", no_wrap=True, justify="left")
    version_table.add_column(no_wrap=True, justify="left")
    for _ in range(5):
        version_table.add_row("", "")
    version_table.add_row(Text(_version_label(version), style="dim"))
    version_table.add_row(
        "FrontPanel",
        Text(_version_label(frontpanel_version), style="dim"),
    )
    header.add_row(Text(MMS_OK_LOGO, style="bold white"), version_table)
    header.add_row("")
    return header


def _bitstream_panel(bitstream_path: str, timestamp: float) -> Panel:
    updated_at = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    body = _kv_table(
        [
            ("File", Text(os.path.basename(bitstream_path), style="bold white")),
            ("Updated", Text(updated_at, style="white")),
            # ("Path", Text(bitstream_path, style="dim")),
            ("Path", Text(bitstream_path, style="white")),
        ]
    )
    return _make_panel("Bitstream", body, "magenta")


def _device_panel(config, vadj_voltage_dict=None) -> Panel:
    board_table = _kv_table(
        [
            ("Model", Text(str(config.product_name), style="bold white")),
            ("Serial", Text(str(config.serial_number), style="white")),
            ("Interface", Text(str(config.device_interface_str), style="white")),
            ("USB Speed", Text(str(config.usb_speed), style="white")),
        ]
    )
    capability_table = _kv_table(
        [
            ("Max Blocksize", Text(str(config.max_bt_blocksize), style="white")),
            ("Wire Width", Text(str(config.wire_width), style="white")),
            ("Trigger Width", Text(str(config.trigger_width), style="white")),
            ("Pipe Width", Text(str(config.pipe_width), style="white")),
        ]
    )

    layout = Table.grid(expand=True, padding=(0, 4))
    layout.add_column(ratio=1)
    layout.add_column(ratio=1)

    headers = [
        Text("[Board]", style="bold white"),
        Text("[Data Path]", style="bold white"),
    ]
    tables = [board_table, capability_table]

    if vadj_voltage_dict:
        voltage_table = _kv_table(
            [
                ("Bank 12 Voltage", Text(f"{vadj_voltage_dict['vadj2']:.2f} V")),
                ("Bank 15 Voltage", Text(f"{vadj_voltage_dict['vadj1']:.2f} V")),
                ("Bank 16 Voltage", Text(f"{vadj_voltage_dict['vadj1']:.2f} V")),
                ("Bank 32 Voltage", Text(f"{vadj_voltage_dict['vadj3']:.2f} V")),
            ]
        )
        layout.add_column(ratio=1)
        headers.append(Text("[I/O Voltage]", style="bold white"))
        tables.append(voltage_table)

    # layout.add_row(*headers)
    layout.add_row(*tables)

    return _make_panel("Device", layout, "blue")


def print_fpga_overview(
    version: str,
    frontpanel_version: str,
    bitstream_path: str,
    bitstream_timestamp: float,
    config,
    vadj_voltage_dict=None,
) -> None:
    layout = Table.grid(expand=True)
    layout.add_column(ratio=1)

    layout.add_row(_header_panel(version, frontpanel_version))
    layout.add_row(_bitstream_panel(bitstream_path, bitstream_timestamp))
    layout.add_row(_device_panel(config, vadj_voltage_dict))

    _panel("", layout, "cyan")
