# test_cursor_converter.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import struct
import sys
import types
import zlib
from pathlib import Path

# Ensure 'flexa' package can be imported from 'src'
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if "flexa" not in sys.modules:
    _pkg = types.ModuleType("flexa")
    _pkg.__path__ = [str(_SRC_DIR)]
    sys.modules["flexa"] = _pkg

from flexa.cursor_converter import (  # noqa: E402
    CursorConverter,
    _frame_to_png,
    _read_xcursor_frames,
    host_path,
)


def _make_converter(output_dir: Path) -> CursorConverter:
    return CursorConverter(
        output_dir=output_dir,
        on_progress=lambda _: None,
        on_all_done=lambda _: None,
    )


def test_parse_inf_maps_aliases_and_ignores_unknown_keys(tmp_path: Path) -> None:
    inf_file = tmp_path / "install.inf"
    inf_file.write_text(
        """
[Version]
signature="$CHICAGO$"

[Strings]
; standard pointer with comments
pointer = "arrow.cur" ; main pointer
; known alias with quoted name and semicolon inside quotes
working = "busy;spinner.ani" ; working alias
; case-insensitive alias
AppStarting = normal_work.ani
; unknown key should be ignored
unknown_key = "ignore.cur"
        """.strip(),
        encoding="utf-8",
    )

    converter = _make_converter(tmp_path)
    mapping = converter._parse_inf(inf_file)

    assert "arrow.cur" in mapping
    assert "arrow" in mapping["arrow.cur"]
    assert "default" in mapping["arrow.cur"]

    assert "busy;spinner.ani" in mapping
    assert "left_ptr_watch" in mapping["busy;spinner.ani"]

    assert "normal_work.ani" in mapping
    assert "progress" in mapping["normal_work.ani"]

    assert "ignore.cur" not in mapping


def test_map_by_filename_accepts_cursor_extensions_case_insensitively(tmp_path: Path) -> None:
    folder = tmp_path / "theme"
    folder.mkdir()
    (folder / "Arrow.CUR").touch()
    (folder / "wait.Ani").touch()
    (folder / "custom.cur").touch()
    (folder / "readme.TXT").touch()
    (folder / "preview.png").touch()

    converter = _make_converter(tmp_path)
    mapping = converter._map_by_filename(folder)

    assert "Arrow.CUR" in mapping
    assert "arrow" in mapping["Arrow.CUR"]

    assert "wait.Ani" in mapping
    assert "wait" in mapping["wait.Ani"]

    assert "custom.cur" in mapping
    assert mapping["custom.cur"] == ["custom"]

    assert "readme.TXT" not in mapping
    assert "preview.png" not in mapping


def test_linux_fallback_validation_accepts_direct_and_nested_cursors(tmp_path: Path) -> None:
    # Direct folder with extensionless cursor files
    direct = tmp_path / "direct_theme"
    direct.mkdir()
    (direct / "arrow").touch()
    assert CursorConverter.is_valid_fallback_path(direct) is True

    # Nested cursors/ folder with extensionless cursor files
    nested = tmp_path / "nested_theme"
    cursors_dir = nested / "cursors"
    cursors_dir.mkdir(parents=True)
    (cursors_dir / "arrow").touch()
    assert CursorConverter.is_valid_fallback_path(nested) is True


def test_fallback_validation_rejects_empty_directories(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_theme"
    empty_dir.mkdir()
    assert CursorConverter.is_valid_fallback_path(empty_dir) is False

    empty_nested = tmp_path / "empty_nested_theme"
    (empty_nested / "cursors").mkdir(parents=True)
    assert CursorConverter.is_valid_fallback_path(empty_nested) is False

    only_extensions = tmp_path / "only_extensions_theme"
    only_extensions.mkdir()
    (only_extensions / "arrow.png").touch()
    assert CursorConverter.is_valid_fallback_path(only_extensions) is False


def test_linux_fallback_copy_preserves_existing_files(tmp_path: Path) -> None:
    fallback = tmp_path / "fallback"
    fallback_cursors = fallback / "cursors"
    fallback_cursors.mkdir(parents=True)

    # Fallback cursors
    (fallback_cursors / "arrow").write_text("fallback_arrow", encoding="utf-8")
    (fallback_cursors / "cross").write_text("fallback_cross", encoding="utf-8")
    (fallback_cursors / "notes.txt").write_text("irrelevant", encoding="utf-8")
    (fallback_cursors / "nested_dir").mkdir()

    # Destination cursors dir
    dest_cursors = tmp_path / "dest" / "cursors"
    dest_cursors.mkdir(parents=True)
    (dest_cursors / "arrow").write_text("existing_arrow", encoding="utf-8")

    converter = _make_converter(tmp_path)
    converter._copy_missing_linux_cursors(fallback, dest_cursors)

    # Existing file must be preserved
    assert (dest_cursors / "arrow").read_text(encoding="utf-8") == "existing_arrow"
    # Missing cursor must be copied
    assert (dest_cursors / "cross").read_text(encoding="utf-8") == "fallback_cross"
    # Irrelevant files must not be copied
    assert not (dest_cursors / "notes.txt").exists()
    assert not (dest_cursors / "nested_dir").exists()


def test_host_path_maps_known_sandbox_icon_paths() -> None:
    # Known sandbox path mapping
    assert (
        host_path("/run/host/share/icons/Adwaita")
        == "/usr/share/icons/Adwaita"
    )
    assert (
        host_path("/run/host/share/icons")
        == "/usr/share/icons"
    )

    # Unrelated path should remain unchanged
    assert (
        host_path("/home/caue/custom/icons")
        == "/home/caue/custom/icons"
    )


def _xcursor_bytes(width: int, height: int, pixels: bytes, *, size: int = 32) -> bytes:
    header = b"Xcur" + struct.pack("<III", 16, 0x10000, 1)
    toc = struct.pack("<III", 0xFFFD0002, size, 28)
    image = struct.pack("<9I", 36, 0xFFFD0002, size, 1, width, height, 1, 2, 50)
    return header + toc + image + pixels


def test_read_xcursor_frames_and_png_unpremultiply(tmp_path: Path) -> None:
    # 2x1 premultiplied BGRA: opaque red, then half-transparent white
    cursor = tmp_path / "arrow"
    cursor.write_bytes(_xcursor_bytes(2, 1, bytes((0, 0, 255, 255, 128, 128, 128, 128))))

    [frame] = _read_xcursor_frames(cursor)
    assert (frame.size, frame.width, frame.height) == (32, 2, 1)
    assert (frame.xhot, frame.yhot, frame.delay) == (1, 2, 50)

    png = _frame_to_png(frame)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (2, 1)
    idat_len = struct.unpack(">I", png[33:37])[0]
    rows = zlib.decompress(png[41 : 41 + idat_len])
    assert rows == bytes((0, 255, 0, 0, 255, 255, 255, 255, 128))


def test_read_xcursor_frames_rejects_truncated_pixels(tmp_path: Path) -> None:
    cursor = tmp_path / "arrow"
    cursor.write_bytes(_xcursor_bytes(2, 2, bytes(4)))

    try:
        _read_xcursor_frames(cursor)
    except ValueError as err:
        assert "truncated" in str(err)
    else:
        raise AssertionError("truncated cursor was accepted")


def test_scalable_cursors_skip_bad_files_and_their_aliases(tmp_path: Path) -> None:
    cursors_dir = tmp_path / "cursors"
    cursors_dir.mkdir()
    (cursors_dir / "arrow").write_bytes(_xcursor_bytes(1, 1, bytes((0, 0, 0, 255))))
    (cursors_dir / "default").symlink_to("arrow")
    (cursors_dir / "wait").write_bytes(_xcursor_bytes(2, 2, bytes(4)))
    (cursors_dir / "watch").symlink_to("wait")

    scalable_dir = tmp_path / "cursors_scalable"
    _make_converter(tmp_path)._write_scalable_cursors(cursors_dir, scalable_dir)

    [entry] = json.loads((scalable_dir / "arrow" / "metadata.json").read_text(encoding="utf-8"))
    assert entry == {
        "filename": "arrow-00.svg",
        "hotspot_x": 1,
        "hotspot_y": 2,
        "nominal_size": 24,
    }
    assert (scalable_dir / "arrow" / "arrow-00.svg").is_file()
    assert (scalable_dir / "default").resolve() == (scalable_dir / "arrow").resolve()
    assert not (scalable_dir / "wait").exists()
    assert not (scalable_dir / "watch").is_symlink()
