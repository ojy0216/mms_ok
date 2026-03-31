import errno
import os
import random
import sys
import time
from secrets import token_hex

from loguru import logger
from rich.console import Console
from rich.table import Table

from .bist_util import btpipe_progress, pipe_progress, trigger_progress, wire_progress
from .fpga import XEM, XEM7310, XEM7360
from .ok_setup import get_ok

console = Console()

PACKAGE_DIR = os.path.dirname(__file__)
PACKAGE_BITSTREAM_DIR = os.path.join(PACKAGE_DIR, "bitstreams")
LEGACY_BITSTREAM_DIR = os.path.expanduser("~/mms_ok/bitstreams")

NUM_TEST_CHANNELS = 32
PIPE_TRANSFER_BYTES = 128 // 8

WIRE_IN_BASE = 0x00
WIRE_OUT_BASE = 0x20
TRIGGER_IN_BASE = 0x40
TRIGGER_OUT_BASE = 0x60
PIPE_IN_BASE = 0x80
PIPE_OUT_BASE = 0xA0

RESET_WIRE_ADDRESS = 0x00
TRIGGER_BIT = 0
TRIGGER_MASK = 0x1


class BIST(XEM):
    def __init__(self):
        ok = get_ok()
        self.xem = ok.okCFrontPanel()

        self._connect()

        logger.info("Initializing BIST...")
        logger.info(f"Product Name: {self.config.product_name}")

        bitstream_dict = {
            "XEM7310-A75": "A75_boardtest.bit",
            "XEM7310-A200": "A200_boardtest.bit",
            "XEM7360-K160T": "K160T_boardtest.bit",
        }

        bitstream_name = bitstream_dict.get(self.config.product_name, None)

        if bitstream_name is None:
            logger.critical(f"Invalid product name: {self.config.product_name}")
            raise ValueError(f"Invalid product name: {self.config.product_name}")

        self._bitstream_path = self._resolve_bitstream_path(bitstream_name)

        self._validate_bitstream_path()

        self.xem.Close()

        self.wire_correct = 0
        self.pipe_correct = 0
        self.btpipe_correct = 0
        self.trigger_correct = 0

    @staticmethod
    def _resolve_bitstream_path(bitstream_name: str) -> str:
        candidate_paths = [
            os.path.join(PACKAGE_BITSTREAM_DIR, bitstream_name),
            os.path.join(LEGACY_BITSTREAM_DIR, bitstream_name),
        ]

        for path in candidate_paths:
            if os.path.isfile(path):
                logger.info(f"Using BIST bitstream: {path}")
                return path

        raise FileNotFoundError(
            "BIST bitstream not found. Checked: {}".format(
                ", ".join(candidate_paths)
            )
        )

    def _check_device_settings(self):
        raise NotImplementedError("Not needed for BIST")

    def SetLED(self, led_value: int, led_address: int = 0x00) -> None:
        raise NotImplementedError("Not needed for BIST")

    def functional_test(self):
        if "XEM7310" in self.config.product_name:
            fpga = XEM7310(self._bitstream_path)
        elif "XEM7360" in self.config.product_name:
            fpga = XEM7360(self._bitstream_path)
        else:
            logger.critical(f"Invalid product name: {self.config.product_name}")
            sys.exit(errno.EINVAL)

        logger.info(f"Running BIST for {self.config.product_name}...")

        """ Wire Test """
        with wire_progress:
            task = wire_progress.add_task("Testing Wires", total=NUM_TEST_CHANNELS)

            for i in range(NUM_TEST_CHANNELS):
                data = random.randint(0, 2**32 - 1)

                fpga.SetWireInValue(ep_addr=WIRE_IN_BASE + i, value=data)

                read_data = fpga.GetWireOutValue(ep_addr=WIRE_OUT_BASE + i)

                if data != read_data:
                    logger.error(f"Error at wire {i}: expected {data}, got {read_data}")
                else:
                    self.wire_correct += 1

                wire_progress.update(task, completed=i + 1)

        console.log(f"Wires correct: {self.wire_correct}/{NUM_TEST_CHANNELS}")

        time.sleep(1)

        """ Pipe Test """
        fpga.reset(reset_address=RESET_WIRE_ADDRESS)

        with pipe_progress:
            task = pipe_progress.add_task("Testing Pipes", total=NUM_TEST_CHANNELS)

            for i in range(NUM_TEST_CHANNELS):
                data = token_hex(PIPE_TRANSFER_BYTES).upper()

                fpga.WriteToPipeIn(ep_addr=PIPE_IN_BASE + i, data=data)

                read_data = fpga.ReadFromPipeOut(
                    ep_addr=PIPE_OUT_BASE + i, data=PIPE_TRANSFER_BYTES
                )

                if data != read_data:
                    logger.error(f"Error at pipe {i}: expected {data}, got {read_data}")
                else:
                    self.pipe_correct += 1

                pipe_progress.update(task, completed=i + 1)

        console.log(f"Pipes correct: {self.pipe_correct}/{NUM_TEST_CHANNELS}")

        time.sleep(1)

        """ BTPipe Test """
        with btpipe_progress:
            task = btpipe_progress.add_task(
                "Testing BTPipes", total=NUM_TEST_CHANNELS
            )

            for i in range(NUM_TEST_CHANNELS):
                data = token_hex(PIPE_TRANSFER_BYTES).upper()

                fpga.WriteToBlockPipeIn(ep_addr=PIPE_IN_BASE + i, data=data)

                read_data = fpga.ReadFromBlockPipeOut(
                    ep_addr=PIPE_OUT_BASE + i, data=PIPE_TRANSFER_BYTES
                )

                if data != read_data:
                    logger.error(
                        f"Error at BTPipe {i}: expected {data}, got {read_data}"
                    )
                else:
                    self.btpipe_correct += 1

                btpipe_progress.update(task, completed=i + 1)

        console.log(f"BTPipes correct: {self.btpipe_correct}/{NUM_TEST_CHANNELS}")

        time.sleep(1)

        """ Trigger Test"""
        with trigger_progress:
            task = trigger_progress.add_task(
                "Testing Triggers", total=NUM_TEST_CHANNELS
            )

            for i in range(NUM_TEST_CHANNELS):
                fpga.ActivateTriggerIn(ep_addr=TRIGGER_IN_BASE + i, bit=TRIGGER_BIT)

                try:
                    fpga.CheckTriggered(
                        ep_addr=TRIGGER_OUT_BASE + i, mask=TRIGGER_MASK
                    )
                except TimeoutError:
                    logger.error(f"Trigger {i} did not fire")
                else:
                    self.trigger_correct += 1

                trigger_progress.update(task, completed=i + 1)

        console.log(f"Triggers correct: {self.trigger_correct}/{NUM_TEST_CHANNELS}\n")

        time.sleep(1)

        fpga.close()

    def print_functional_test_results(self):
        table = Table(title="Functional Test Results")
        table.add_column("Test", justify="center")
        table.add_column("Result", justify="center")

        table.add_row(
            "Wires",
            (
                f"[green]Passed {self.wire_correct}/32[/green]"
                if self.wire_correct == NUM_TEST_CHANNELS
                else f"[red]Failed {self.wire_correct}/{NUM_TEST_CHANNELS}[/red]"
            ),
        )
        table.add_row(
            "Pipes",
            (
                f"[green]Passed {self.pipe_correct}/32[/green]"
                if self.pipe_correct == NUM_TEST_CHANNELS
                else f"[red]Failed {self.pipe_correct}/{NUM_TEST_CHANNELS}[/red]"
            ),
        )
        table.add_row(
            "BTPipes",
            (
                f"[green]Passed {self.btpipe_correct}/32[/green]"
                if self.btpipe_correct == NUM_TEST_CHANNELS
                else f"[red]Failed {self.btpipe_correct}/{NUM_TEST_CHANNELS}[/red]"
            ),
        )
        table.add_row(
            "Triggers",
            (
                f"[green]Passed {self.trigger_correct}/32[/green]"
                if self.trigger_correct == NUM_TEST_CHANNELS
                else f"[red]Failed {self.trigger_correct}/{NUM_TEST_CHANNELS}[/red]"
            ),
        )

        console.print(table)

    def run_test(self):
        self.functional_test()
        self.print_functional_test_results()
