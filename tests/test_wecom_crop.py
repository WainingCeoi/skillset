"""Synthetic exact-pixel screenshot crops, with no access to a live UI."""
from __future__ import annotations

from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/wecom-chat-capture"
sys.path.insert(0, str(SKILL / "scripts"))
import chat_package as cp
import crop_preview as crop


def chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)


def parts(png):
    result, offset = [], 8
    while offset < len(png):
        length = struct.unpack_from(">I", png, offset)[0]
        result.append((png[offset + 4:offset + 8], png[offset + 8:offset + 8 + length]))
        offset += length + 12
    return result


def invented_image(channels=3, modes=(0, 1, 2, 3, 4, 0), metadata=()):
    width, height = 7, len(modes)
    rows = [bytes((x * 73 + y * 109 + c * 47) % 256 for x in range(width) for c in range(channels))
            for y in range(height)]
    filtered = []
    for y, (row, mode) in enumerate(zip(rows, modes)):
        encoded = bytearray()
        for i, value in enumerate(row):
            a = row[i - channels] if i >= channels else 0
            b = rows[y - 1][i] if y else 0
            c = rows[y - 1][i - channels] if y and i >= channels else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            predicted = a if pa <= pb and pa <= pc else b if pb <= pc else c
            predictor = {0: 0, 1: a, 2: b, 3: (a + b) // 2, 4: predicted}[mode]
            encoded.append((value - predictor) % 256)
        filtered.append(bytes([mode]) + encoded)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8,
            2 if channels == 3 else 6, 0, 0, 0)) + b"".join(chunk(*item) for item in metadata)
           + chunk(b"IDAT", zlib.compress(b"".join(filtered))) + chunk(b"IEND", b""))
    return png, rows


class CropTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "screenshot.png"

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_rgb_and_alpha_pixels_for_every_png_filter(self):
        for channels in (3, 4):
            for mode in range(5):
                with self.subTest(channels=channels, mode=mode):
                    png, rows = invented_image(channels, (mode,) * 6)
                    result = crop.crop_png(png, (2, 1, 4, 3))
                    self.assertEqual(cp.static_png_size(result), (4, 3))
                    payload = zlib.decompress(b"".join(data for kind, data in parts(result) if kind == b"IDAT"))
                    expected = b"".join(b"\0" + row[2 * channels:6 * channels] for row in rows[1:4])
                    self.assertEqual(payload, expected)
                    self.assertEqual(parts(result)[0][1][9], 2 if channels == 3 else 6)

    def test_mixed_filters_edge_crop_and_whole_image_preserve_pixels(self):
        png, rows = invented_image(4)
        for box in ((0, 0, 7, 6), (0, 0, 1, 1), (6, 5, 1, 1), (0, 2, 7, 2)):
            x, y, width, height = box
            result = crop.crop_png(png, box)
            payload = zlib.decompress(b"".join(data for kind, data in parts(result) if kind == b"IDAT"))
            self.assertEqual(payload, b"".join(b"\0" + row[x * 4:(x + width) * 4] for row in rows[y:y + height]))
            self.assertEqual(result, crop.crop_png(png, box))

    def test_color_and_transparency_chunks_survive_without_private_text_metadata(self):
        metadata = [(b"sRGB", b"\0"), (b"gAMA", struct.pack(">I", 45455)),
                    (b"cHRM", struct.pack(">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000)),
                    (b"tRNS", struct.pack(">HHH", 20, 40, 60)), (b"tEXt", b"Private\0do not carry screenshot notes")]
        png, _ = invented_image(metadata=metadata)
        result = crop.crop_png(png, (1, 1, 2, 2))
        self.assertEqual([(kind, value) for kind, value in parts(result) if kind in {item[0] for item in metadata}],
                         metadata[:-1])
        profile = (b"iCCP", b"invented\0\0" + zlib.compress(b"synthetic profile payload"))
        png, _ = invented_image(metadata=[profile])
        self.assertIn(profile, parts(crop.crop_png(png, (0, 0, 1, 1))))

    def test_bad_bounds_corruption_and_animation_leave_no_output(self):
        png, _ = invented_image()
        self.source.write_bytes(png)
        output = self.root / "crop.png"
        for box in ((-1, 0, 2, 2), (0, -1, 2, 2), (0, 0, 0, 2), (0, 0, 2, -1),
                    (6, 5, 2, 2), (7, 0, 1, 1), (True, 0, 1, 1)):
            with self.subTest(box=box), self.assertRaises(cp.Invalid):
                crop.crop_file(self.source, box, output)
            self.assertFalse(output.exists())
        bad = (png[:-1], png + b"private trailing bytes",
               png[:33] + chunk(b"acTL", struct.pack(">II", 1, 0)) + png[33:],
               png[:45] + bytes([png[45] ^ 1]) + png[46:])
        for data in bad:
            self.source.write_bytes(data)
            with self.assertRaises(cp.Invalid):
                crop.crop_file(self.source, (0, 0, 1, 1), output)
            self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".wecom-crop-*")), [])

    def test_file_and_cli_outputs_are_private_deterministic_and_never_overwrite(self):
        png, _ = invented_image(4)
        self.source.write_bytes(png)
        output = self.root / "cropped.png"
        command = [sys.executable, str(SKILL / "scripts/crop_preview.py"), str(self.source),
                   "--box", "2", "1", "4", "3", "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = cp.strict_json(result.stdout)
        self.assertEqual((report["width"], report["height"]), (4, 3))
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual(output.read_bytes(), crop.crop_png(png, (2, 1, 4, 3)))
        self.assertEqual(self.source.read_bytes(), png)
        before = output.read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        with self.assertRaises(cp.Invalid):
            crop.crop_file(self.source, (0, 0, 1, 1), self.source)
        self.assertEqual(self.source.read_bytes(), png)

    def test_atomic_publish_failure_removes_temporary_file(self):
        png, _ = invented_image()
        self.source.write_bytes(png)
        output = self.root / "crop.png"
        with patch.object(crop.os, "link", side_effect=OSError("synthetic publish failure")), self.assertRaises(OSError):
            crop.crop_file(self.source, (0, 0, 1, 1), output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".wecom-crop-*")), [])


if __name__ == "__main__":
    unittest.main()
