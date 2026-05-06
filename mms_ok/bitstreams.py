"""Bitstream path resolution helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List

PACKAGE_DIR = os.path.dirname(__file__)
PACKAGE_BITSTREAM_DIR = os.path.join(PACKAGE_DIR, "bitstreams")
LEGACY_BITSTREAM_DIR = os.path.expanduser("~/mms_ok/bitstreams")
USER_BITSTREAM_BASE_DIR = os.path.join("..", "bitstreams")


@dataclass(frozen=True)
class BitstreamResolution:
    path: str
    checked_paths: List[str]


def _normalize(path: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def user_bitstream_candidates(bitstream_path: str) -> List[str]:
    expanded = os.path.expandvars(os.path.expanduser(bitstream_path))
    if os.path.isabs(expanded):
        return [_normalize(expanded)]
    return [os.path.abspath(os.path.join(os.getcwd(), USER_BITSTREAM_BASE_DIR, expanded))]


def resolve_user_bitstream_path(bitstream_path: str) -> BitstreamResolution:
    checked_paths = user_bitstream_candidates(bitstream_path)
    return BitstreamResolution(path=checked_paths[0], checked_paths=checked_paths)


def bist_bitstream_candidates(bitstream_name: str) -> List[str]:
    return [
        os.path.join(PACKAGE_BITSTREAM_DIR, bitstream_name),
        os.path.join(LEGACY_BITSTREAM_DIR, bitstream_name),
    ]


def first_existing_path(candidate_paths: Iterable[str]) -> BitstreamResolution:
    checked_paths = [os.path.abspath(path) for path in candidate_paths]
    for path in checked_paths:
        if os.path.isfile(path):
            return BitstreamResolution(path=path, checked_paths=checked_paths)
    return BitstreamResolution(path=checked_paths[0], checked_paths=checked_paths)


def format_checked_paths(paths: Iterable[str]) -> str:
    return ", ".join(str(path) for path in paths)
