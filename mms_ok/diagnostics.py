"""Diagnostics helpers for error logging."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Optional

from loguru import logger


PACKAGE_DIR = Path(__file__).resolve().parent


def _external_caller() -> Optional[str]:
    for frame in inspect.stack()[2:]:
        filename = frame.filename
        if filename.startswith("<") and filename.endswith(">"):
            return f"{filename}:{frame.lineno} in {frame.function}()"

        try:
            frame_path = Path(filename).resolve()
            frame_path.relative_to(PACKAGE_DIR)
        except ValueError:
            return f"{frame_path}:{frame.lineno} in {frame.function}()"
        except OSError:
            return f"{filename}:{frame.lineno} in {frame.function}()"
    return None


def log_error(message: str) -> None:
    logger.error(message)
    caller = _external_caller()
    if caller is not None:
        logger.error(f"Origin: {caller}")


def log_critical(message: str) -> None:
    logger.critical(message)
    caller = _external_caller()
    if caller is not None:
        logger.critical(f"Origin: {caller}")
