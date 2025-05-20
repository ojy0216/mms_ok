import errno
import os
import random
import sys
import time
from secrets import token_hex

import ok
import pkg_resources
from loguru import logger
from rich.console import Console
from rich.table import Table

from .bist_util import btpipe_progress, pipe_progress, trigger_progress, wire_progress
from .fpga import XEM, XEM7310, XEM7360

console = Console()


class BIST(XEM):
    def __init__(self):
        self.xem = ok.okCFrontPanel()

        self._connect()

        logger.info("Initializing BIST...")
        logger.info(f"Product Name: {self.config.product_name}")

        # Get the package directory
        self.package_dir = os.path.dirname(
            pkg_resources.resource_filename(__name__, "__init__.py")
        )

        bitstream_dict = {
            "XEM7310-A75": os.path.join(
                self.package_dir, "bitstreams", "A75_boardtest.bit"
            ),
            "XEM7310-A200": os.path.join(
                self.package_dir, "bitstreams", "A200_boardtest.bit"
            ),
            "XEM7360-K160T": os.path.join(
                self.package_dir, "bitstreams", "K160T_boardtest.bit"
            ),
        }

        self._bitstream_path = bitstream_dict.get(self.config.product_name, None)

        if self._bitstream_path is None:
            logger.critical(f"Invalid product name: {self.config.product_name}")

        self._validate_bitstream_path()

        self.xem.Close()

        self.wire_correct = 0
        self.pipe_correct = 0
        self.btpipe_correct = 0
        self.trigger_correct = 0

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
            task = wire_progress.add_task("Testing Wires", total=32)

            for i in range(32):
                data = random.randint(0, 2**32 - 1)

                fpga.SetWireInValue(ep_addr=i, value=data)

                read_data = fpga.GetWireOutValue(ep_addr=0x20 + i)

                if data != read_data:
                    logger.error(f"Error at wire {i}: expected {data}, got {read_data}")
                else:
                    self.wire_correct += 1

                wire_progress.update(task, completed=i + 1)

        console.log(f"Wires correct: {self.wire_correct}/32")

        time.sleep(1)

        """ Pipe Test """
        fpga.reset(reset_address=0)

        with pipe_progress:
            task = pipe_progress.add_task("Testing Pipes", total=32)

            for i in range(32):
                data = token_hex(128 // 8).upper()

                fpga.WriteToPipeIn(ep_addr=0x80 + i, data=data)

                read_data = fpga.ReadFromPipeOut(ep_addr=0xA0 + i, data=128 // 8)

                if data != read_data:
                    logger.error(f"Error at pipe {i}: expected {data}, got {read_data}")
                else:
                    self.pipe_correct += 1

                pipe_progress.update(task, completed=i + 1)

        console.log(f"Pipes correct: {self.pipe_correct}/32")

        time.sleep(1)

        """ BTPipe Test """
        with btpipe_progress:
            task = btpipe_progress.add_task("Testing BTPipes", total=32)

            for i in range(32):
                data = token_hex(128 // 8).upper()

                fpga.WriteToBlockPipeIn(ep_addr=0x80 + i, data=data)

                read_data = fpga.ReadFromBlockPipeOut(ep_addr=0xA0 + i, data=128 // 8)

                if data != read_data:
                    logger.error(
                        f"Error at BTPipe {i}: expected {data}, got {read_data}"
                    )
                else:
                    self.btpipe_correct += 1

                btpipe_progress.update(task, completed=i + 1)

        console.log(f"BTPipes correct: {self.btpipe_correct}/32")

        time.sleep(1)

        """ Trigger Test"""
        with trigger_progress:
            task = trigger_progress.add_task("Testing Triggers", total=32)

            for i in range(32):
                fpga.ActivateTriggerIn(ep_addr=0x40 + i, bit=0)

                try:
                    fpga.CheckTriggered(ep_addr=0x60 + i, mask=0x1)
                except TimeoutError:
                    logger.error(f"Trigger {i} did not fire")
                else:
                    self.trigger_correct += 1

                trigger_progress.update(task, completed=i + 1)

        console.log(f"Triggers correct: {self.trigger_correct}/32\n")

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
                if self.wire_correct == 32
                else f"[red]Failed {self.wire_correct}/32[/red]"
            ),
        )
        table.add_row(
            "Pipes",
            (
                f"[green]Passed {self.pipe_correct}/32[/green]"
                if self.pipe_correct == 32
                else f"[red]Failed {self.pipe_correct}/32[/red]"
            ),
        )
        table.add_row(
            "BTPipes",
            (
                f"[green]Passed {self.btpipe_correct}/32[/green]"
                if self.btpipe_correct == 32
                else f"[red]Failed {self.btpipe_correct}/32[/red]"
            ),
        )
        table.add_row(
            "Triggers",
            (
                f"[green]Passed {self.trigger_correct}/32[/green]"
                if self.trigger_correct == 32
                else f"[red]Failed {self.trigger_correct}/32[/red]"
            ),
        )

        console.print(table)

    def run_test(self):
        self.functional_test()
        self.print_functional_test_results()
