from __future__ import annotations

import pytest

from mms_ok import bist
from mms_ok import bitstreams


def test_user_resolver_accepts_absolute_bitstream_path(tmp_path):
    bitstream = tmp_path / "design.bit"
    bitstream.write_bytes(b"absolute")

    resolution = bitstreams.resolve_user_bitstream_path(str(bitstream))

    assert resolution.path == str(bitstream.resolve())
    assert resolution.checked_paths == [str(bitstream.resolve())]


def test_user_resolver_uses_parent_bitstreams_for_filename(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    parent_bitstream_dir = tmp_path / "bitstreams"
    work_dir.mkdir()
    parent_bitstream_dir.mkdir()
    cwd_bitstream = work_dir / "design.bit"
    parent_bitstream = parent_bitstream_dir / "design.bit"
    cwd_bitstream.write_bytes(b"cwd")
    parent_bitstream.write_bytes(b"parent")
    monkeypatch.chdir(work_dir)

    resolution = bitstreams.resolve_user_bitstream_path("design.bit")

    assert resolution.path == str(parent_bitstream.resolve())
    assert resolution.checked_paths == [str(parent_bitstream.resolve())]


def test_user_resolver_uses_cwd_for_directory_relative_path(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    bitstream_dir = work_dir / "subdir"
    work_dir.mkdir()
    bitstream_dir.mkdir()
    bitstream = bitstream_dir / "design.bit"
    bitstream.write_bytes(b"relative")
    monkeypatch.chdir(work_dir)

    resolution = bitstreams.resolve_user_bitstream_path("subdir/design.bit")

    assert resolution.path == str(bitstream.resolve())
    assert resolution.checked_paths == [str(bitstream.resolve())]


def test_user_resolver_uses_cwd_for_current_directory_path(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    parent_bitstream_dir = tmp_path / "bitstreams"
    work_dir.mkdir()
    parent_bitstream_dir.mkdir()
    cwd_bitstream = work_dir / "design.bit"
    parent_bitstream = parent_bitstream_dir / "design.bit"
    cwd_bitstream.write_bytes(b"cwd")
    parent_bitstream.write_bytes(b"parent")
    monkeypatch.chdir(work_dir)

    resolution = bitstreams.resolve_user_bitstream_path("./design.bit")

    assert resolution.path == str(cwd_bitstream.resolve())
    assert resolution.checked_paths == [str(cwd_bitstream.resolve())]


def test_user_resolver_expands_env_before_directory_relative_check(
    monkeypatch, tmp_path
):
    work_dir = tmp_path / "work"
    bitstream_dir = work_dir / "subdir"
    work_dir.mkdir()
    bitstream_dir.mkdir()
    bitstream = bitstream_dir / "design.bit"
    bitstream.write_bytes(b"env relative")
    monkeypatch.chdir(work_dir)
    monkeypatch.setenv("MMS_OK_TEST_BITSTREAM_DIR", "subdir")

    resolution = bitstreams.resolve_user_bitstream_path(
        "$MMS_OK_TEST_BITSTREAM_DIR/design.bit"
    )

    assert resolution.path == str(bitstream.resolve())
    assert resolution.checked_paths == [str(bitstream.resolve())]


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


def test_bist_resolver_falls_back_to_legacy_bitstream(monkeypatch, tmp_path):
    package_dir = tmp_path / "package"
    legacy_dir = tmp_path / "legacy"
    package_dir.mkdir()
    legacy_dir.mkdir()
    legacy_bitstream = legacy_dir / "board.bit"
    legacy_bitstream.write_bytes(b"legacy")

    monkeypatch.setattr(bitstreams, "PACKAGE_BITSTREAM_DIR", str(package_dir))
    monkeypatch.setattr(bitstreams, "LEGACY_BITSTREAM_DIR", str(legacy_dir))

    assert bist.BIST._resolve_bitstream_path("board.bit") == str(
        legacy_bitstream.resolve()
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
