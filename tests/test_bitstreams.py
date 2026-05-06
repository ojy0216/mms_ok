from __future__ import annotations

import pytest

from mms_ok import bist
from mms_ok import bitstreams


def test_bist_resolver_prefers_packaged_bitstream(monkeypatch, tmp_path):
    package_dir = tmp_path / "package"
    legacy_dir = tmp_path / "legacy"
    package_dir.mkdir()
    legacy_dir.mkdir()
    package_bitstream = package_dir / "board.bit"
    legacy_bitstream = legacy_dir / "board.bit"
    package_bitstream.write_bytes(b"package")
    legacy_bitstream.write_bytes(b"legacy")

    monkeypatch.setattr(bitstreams, "PACKAGE_BITSTREAM_DIR", str(package_dir))
    monkeypatch.setattr(bitstreams, "LEGACY_BITSTREAM_DIR", str(legacy_dir))

    assert bist.BIST._resolve_bitstream_path("board.bit") == str(
        package_bitstream.resolve()
    )


def test_bist_resolver_reports_checked_paths(monkeypatch, tmp_path):
    package_dir = tmp_path / "package"
    legacy_dir = tmp_path / "legacy"

    monkeypatch.setattr(bitstreams, "PACKAGE_BITSTREAM_DIR", str(package_dir))
    monkeypatch.setattr(bitstreams, "LEGACY_BITSTREAM_DIR", str(legacy_dir))

    with pytest.raises(FileNotFoundError) as exc_info:
        bist.BIST._resolve_bitstream_path("missing.bit")

    message = str(exc_info.value)
    assert str((package_dir / "missing.bit").resolve()) in message
    assert str((legacy_dir / "missing.bit").resolve()) in message
