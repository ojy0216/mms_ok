import os
import random
import time
from secrets import token_hex

from loguru import logger
from rich.console import Console
from rich.table import Table

from .address import (
    BLOCK_PIPE_IN_START,
    BLOCK_PIPE_OUT_START,
    PIPE_IN_START,
    PIPE_OUT_START,
    TRIGGER_IN_START,
    TRIGGER_OUT_START,
    WIRE_IN_START,
    WIRE_OUT_START,
)
from .bist_util import btpipe_progress, pipe_progress, trigger_progress, wire_progress
from .fpga import XEM7310, XEM7360
from .fpga_config import FPGAConfig
from .ok_setup import get_ok

console = Console()

PACKAGE_DIR = os.path.dirname(__file__)
PACKAGE_BITSTREAM_DIR = os.path.join(PACKAGE_DIR, "bitstreams")
LEGACY_BITSTREAM_DIR = os.path.expanduser("~/mms_ok/bitstreams")

NUM_TEST_CHANNELS = 32
PIPE_TRANSFER_BYTES = 128 // 8

RESET_WIRE_ADDRESS = WIRE_IN_START
TRIGGER_BIT = 0
TRIGGER_MASK = 0x1

BIST_BITSTREAMS = {
    "XEM7310-A75": "A75_boardtest.bit",
    "XEM7310-A200": "A200_boardtest.bit",
    "XEM7360-K160T": "K160T_boardtest.bit",
}


class BIST:
    def __init__(self):
        logger.info("Initializing BIST...")
        self.config = self._detect_config()
        logger.info(f"Detected BIST target: {self.config.product_name}")

        bitstream_name = BIST_BITSTREAMS.get(self.config.product_name)
        if bitstream_name is None:
            logger.critical(f"Invalid product name: {self.config.product_name}")
            raise ValueError(f"Invalid product name: {self.config.product_name}")

        self._bitstream_path = self._resolve_bitstream_path(bitstream_name)
        self._validate_bitstream_path()

        self.wire_correct = 0
        self.pipe_correct = 0
        self.btpipe_correct = 0
        self.trigger_correct = 0

    @staticmethod
    def _detect_config() -> FPGAConfig:
        ok = get_ok()
        xem = ok.okCFrontPanel()

        try:
            if xem.OpenBySerial(""):
                logger.critical("Device is not opened!")
                raise ConnectionError("Device is not opened!")

            device_info = ok.okTDeviceInfo()
            xem.GetDeviceInfo(device_info)
            return FPGAConfig.from_device_info(device_info)
        finally:
            xem.Close()

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

    def _validate_bitstream_path(self) -> None:
        if not os.path.isfile(self._bitstream_path):
            logger.critical(f'"{self._bitstream_path}" is invalid!')
            raise FileNotFoundError(f"{self._bitstream_path} is an invalid bitstream!")

        extension = os.path.splitext(self._bitstream_path)[1]
        if extension != ".bit":
            logger.critical(f"{extension} is not a valid bitstream file extension!")
            raise ValueError(f"{extension} is not a valid bitstream file extension!")

    def _create_fpga(self):
        if "XEM7310" in self.config.product_name:
            return XEM7310(self._bitstream_path)
        if "XEM7360" in self.config.product_name:
            return XEM7360(self._bitstream_path)

        logger.critical(f"Invalid product name: {self.config.product_name}")
        raise ValueError(f"Invalid product name: {self.config.product_name}")

    def functional_test(self):
        fpga = self._create_fpga()

        logger.info(f"Running BIST for {self.config.product_name}...")

        try:
            self._run_wire_test(fpga)
            time.sleep(1)

            self._run_pipe_test(fpga)
            time.sleep(1)

            self._run_block_pipe_test(fpga)
            time.sleep(1)

            self._run_trigger_test(fpga)
            time.sleep(1)
        finally:
            fpga.close()

    def _run_wire_test(self, fpga) -> None:
        with wire_progress:
            task = wire_progress.add_task("Testing Wires", total=NUM_TEST_CHANNELS)

            for i in range(NUM_TEST_CHANNELS):
                data = random.randint(0, 2**32 - 1)

                fpga.SetWireInValue(ep_addr=WIRE_IN_START + i, value=data)
                read_data = fpga.GetWireOutValue(ep_addr=WIRE_OUT_START + i)

                if data != read_data:
                    logger.error(f"Error at wire {i}: expected {data}, got {read_data}")
                else:
                    self.wire_correct += 1

                wire_progress.update(task, completed=i + 1)

        console.log(f"Wires correct: {self.wire_correct}/{NUM_TEST_CHANNELS}")

    def _run_pipe_test(self, fpga) -> None:
        fpga.reset(reset_address=RESET_WIRE_ADDRESS)

        with pipe_progress:
            task = pipe_progress.add_task("Testing Pipes", total=NUM_TEST_CHANNELS)

            for i in range(NUM_TEST_CHANNELS):
                data = token_hex(PIPE_TRANSFER_BYTES).upper()

                fpga.WriteToPipeIn(ep_addr=PIPE_IN_START + i, data=data)
                read_data = fpga.ReadFromPipeOut(
                    ep_addr=PIPE_OUT_START + i, data=PIPE_TRANSFER_BYTES
                )

                if data != read_data:
                    logger.error(f"Error at pipe {i}: expected {data}, got {read_data}")
                else:
                    self.pipe_correct += 1

                pipe_progress.update(task, completed=i + 1)

        console.log(f"Pipes correct: {self.pipe_correct}/{NUM_TEST_CHANNELS}")

    def _run_block_pipe_test(self, fpga) -> None:
        with btpipe_progress:
            task = btpipe_progress.add_task("Testing BTPipes", total=NUM_TEST_CHANNELS)

            for i in range(NUM_TEST_CHANNELS):
                data = token_hex(PIPE_TRANSFER_BYTES).upper()

                fpga.WriteToBlockPipeIn(ep_addr=BLOCK_PIPE_IN_START + i, data=data)
                read_data = fpga.ReadFromBlockPipeOut(
                    ep_addr=BLOCK_PIPE_OUT_START + i, data=PIPE_TRANSFER_BYTES
                )

                if data != read_data:
                    logger.error(
                        f"Error at BTPipe {i}: expected {data}, got {read_data}"
                    )
                else:
                    self.btpipe_correct += 1

                btpipe_progress.update(task, completed=i + 1)

        console.log(f"BTPipes correct: {self.btpipe_correct}/{NUM_TEST_CHANNELS}")

    def _run_trigger_test(self, fpga) -> None:
        with trigger_progress:
            task = trigger_progress.add_task(
                "Testing Triggers", total=NUM_TEST_CHANNELS
            )

            for i in range(NUM_TEST_CHANNELS):
                fpga.ActivateTriggerIn(ep_addr=TRIGGER_IN_START + i, bit=TRIGGER_BIT)

                try:
                    fpga.CheckTriggered(
                        ep_addr=TRIGGER_OUT_START + i, mask=TRIGGER_MASK
                    )
                except TimeoutError:
                    logger.error(f"Trigger {i} did not fire")
                else:
                    self.trigger_correct += 1

                trigger_progress.update(task, completed=i + 1)

        console.log(f"Triggers correct: {self.trigger_correct}/{NUM_TEST_CHANNELS}\n")

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
