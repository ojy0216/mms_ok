"""Diagnostics helpers for error logging."""

from __future__ import annotations

import inspect
import os
from typing import Optional

from loguru import logger


PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))


def _is_package_path(filename: str) -> bool:
    try:
        frame_path = os.path.abspath(filename)
        return os.path.commonpath([PACKAGE_DIR, frame_path]) == PACKAGE_DIR
    except (OSError, ValueError):
        return False


def _external_caller() -> Optional[str]:
    for frame in inspect.stack()[2:]:
        filename = frame.filename
        if filename.startswith("<") and filename.endswith(">"):
            return f"{filename}:{frame.lineno} in {frame.function}()"

        try:
            frame_path = os.path.abspath(filename)
        except OSError:
            return f"{filename}:{frame.lineno} in {frame.function}()"

        if not _is_package_path(filename):
            return f"{frame_path}:{frame.lineno} in {frame.function}()"
    return None


def log_error(message: str) -> None:
    logger.error(message)
    caller = _external_caller()
    if caller is not None:
        logger.error(f"Origin: {caller}")


def log_warning(message: str) -> None:
    logger.warning(message)
    caller = _external_caller()
    if caller is not None:
        logger.warning(f"Origin: {caller}")


def log_critical(message: str) -> None:
    logger.critical(message)
    caller = _external_caller()
    if caller is not None:
        logger.critical(f"Origin: {caller}")
