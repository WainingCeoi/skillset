"""Synthetic sticker preparation and visible-representation delivery checks."""
from __future__ import annotations

import copy
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/wecom-chat-capture"
sys.path.insert(0, str(SKILL / "scripts"))
import chat_package as cp
from make_voice_synthetic import invented_png


GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
       b"!\xf9\x04\x00\x04\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00"
       b"!\xf9\x04\x00\x09\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00;")


class StickerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.batch = self.root / "batch"
        self.media = self.batch / "media"
        self.crop = self.root / "invented.png"
        self.crop.write_bytes(invented_png())

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, index=0):
        provenance = {"source": "synthetic", "capture_method": "invented observation",
                      "locator": f"synthetic:viewport-1/sticker-{index}", "notes": "No real chat data."}
        return {"message": {"id": f"sticker-{index}", "id_kind": "generated", "source_id": None,
                            "sender": {"id": None, "name": "合成成员", "is_self": False},
                            "sent_at": None, "original_time": None, "order": index,
                            "type": "sticker", "text": None, "reply_to": None, "media": [],
                            "provenance": provenance},
                "sticker": {"file": None, "original_name": None,
                            "missing_reason": "Synthetic export action unavailable.",
                            "preview": {"file": str(self.crop), "provenance": {
                                "source": "synthetic", "capture_method": "invented static crop",
                                "locator": f"synthetic:sticker-{index}", "notes": "One observed state only."}}}}

    def package(self, records):
        self.media.mkdir(parents=True, exist_ok=True)
        attachments = [a for record in records for a in record["attachments"]]
        manifest = {"version": cp.VERSION, "conversation_id": "synthetic-stickers", "title": "Invented stickers",
                    "batch_id": "synthetic-sticker-baseline", "base_batch_id": None,
                    "capture": {"started_at": None, "ended_at": None, "captured_at": "2026-10-21T15:00:00+08:00",
                                "timezone": "Asia/Shanghai"},
                    "counts": {"messages": len(records), "attachments": len(attachments)},
                    "attachments": attachments,
                    "completeness": {"history": "partial", "attachments": "partial",
                                     "notes": ["Synthetic original gaps; static previews preserve only visible states."]},
                    "provenance": {"source": "synthetic", "capture_method": "invented fixtures"}, "overlap_anchors": []}
        (self.batch / "manifest.json").write_bytes(cp.encoded(manifest))
        (self.batch / "messages.jsonl").write_bytes(b"".join(cp.encoded(record["message"]) for record in records))
        return cp.load_bundle(self.batch)[0]

    def test_static_fallback_keeps_gap_and_pixels_across_zip_roundtrip(self):
        record = cp.prepare_sticker_record(self.spec(), self.media)
        original, preview = record["attachments"]
        self.assertEqual(original["content_type"], "application/octet-stream")
        self.assertIsNone(original["original_name"])
        self.assertEqual(original["completeness"], "missing")
        self.assertEqual(preview["derived_from"], original["path"])
        self.assertEqual(preview["role"], "screenshot_preview")
        self.assertEqual(len(record["message"]["media"]), 2)
        self.assertIsNone(record["message"]["text"])
        self.assertIsNone(record["message"]["sent_at"])
        self.assertIsNone(record["message"]["original_time"])
        package = self.package([record])
        self.assertEqual(cp.preview(package, {})["sticker_visuals"][0]["status"], "static_preview")
        cp.require_sticker_visual(package)
        archive = self.root / "stickers.zip"
        cp.create_zip(package, archive)
        restored = cp.load_bundle(archive)[0]
        self.assertNotIn(original["path"], restored.entries)
        self.assertEqual(restored.entries[preview["path"]], self.crop.read_bytes())
        self.assertEqual(restored.messages, package.messages)
        self.assertEqual(restored.manifest["completeness"]["attachments"], "partial")

    def test_saved_animation_unchanged_and_extension_never_determines_mime(self):
        for index, (data, expected) in enumerate(((GIF, "image/gif"), (invented_png(), "image/png"),
                                                  (b"opaque proprietary sticker bytes", "application/octet-stream"))):
            saved = self.root / f"misleading-{index}.gif"
            saved.write_bytes(data)
            spec = self.spec(index)
            spec["sticker"].update(file=str(saved), original_name="原始显示名", missing_reason=None, preview=None)
            record = cp.prepare_sticker_record(spec, self.media)
            item = record["attachments"][0]
            self.assertEqual(item["content_type"], expected)
            self.assertEqual((self.media / Path(item["path"]).name).read_bytes(), data)
            self.assertEqual(saved.read_bytes(), data)
            self.assertEqual(item["original_name"], "原始显示名")
            self.assertEqual(item["role"], "original")

    def test_byte_format_checks_reject_truncated_known_containers(self):
        # Framing-only synthetic WebP header: decoder/playability is outside this helper.
        chunk = b"VP8L" + struct.pack("<I", 5) + b"\x2f\x00\x00\x00\x00" + b"\x00"
        webp = b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk
        self.assertEqual(cp.original_sticker_type(webp), "image/webp")
        for data in (GIF[:-1], invented_png()[:-1], webp[:-1], b"GIF89a", b""):
            with self.subTest(data=data[:10]), self.assertRaises(cp.Invalid):
                cp.original_sticker_type(data)

    def test_visual_guard_separates_available_preview_and_unavailable_occurrences(self):
        saved = self.root / "original.bin"
        saved.write_bytes(GIF)
        original = self.spec(0)
        original["sticker"].update(file=str(saved), missing_reason=None, preview=None)
        unavailable = self.spec(2)
        unavailable["sticker"]["preview"] = None
        records = [cp.prepare_sticker_record(spec, self.media) for spec in (original, self.spec(1), unavailable)]
        package = self.package(records)
        self.assertEqual([r["status"] for r in cp.sticker_visuals(package)],
                         ["original_available", "static_preview", "visual_missing"])
        with self.assertRaisesRegex(cp.Invalid, "sticker-2"):
            cp.require_sticker_visual(package)
        output = self.root / "guarded.zip"
        command = [sys.executable, str(SKILL / "scripts/chat_package.py"), "pack", str(self.batch),
                   "--output", str(output), "--require-sticker-visual"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sticker-2", result.stderr)
        self.assertFalse(output.exists())
        self.assertEqual(subprocess.run(command[:-1], capture_output=True).returncode, 0)
        self.assertEqual(len(cp.load_bundle(output)[0].messages), 3)

    def test_opaque_and_mime_spoofed_originals_stay_preserved_without_visual_coverage(self):
        records = []
        for index in range(2):
            data = b"invented proprietary sticker bytes " + bytes([index])
            saved = self.root / f"opaque-{index}.png"
            saved.write_bytes(data)
            spec = self.spec(index)
            spec["sticker"].update(file=str(saved), missing_reason=None, preview=None)
            record = cp.prepare_sticker_record(spec, self.media)
            if index == 1:
                record["attachments"][0]["content_type"] = "image/png"
            records.append(record)
        package = self.package(records)
        report = cp.sticker_visuals(package)
        self.assertEqual([item["status"] for item in report], ["visual_missing", "visual_missing"])
        self.assertTrue(all("bytes preserved" in item["reason"] for item in report))
        with self.assertRaises(cp.Invalid):
            cp.require_sticker_visual(package)
        archive = self.root / "opaque-preserved.zip"
        cp.create_zip(package, archive)
        restored = cp.load_bundle(archive)[0]
        for index, record in enumerate(records):
            item = record["attachments"][0]
            self.assertEqual(item["completeness"], "complete")
            self.assertEqual(restored.entries[item["path"]], b"invented proprietary sticker bytes " + bytes([index]))

    def test_visual_guard_resolves_explicit_prior_original_bytes(self):
        saved = self.root / "original.bin"
        saved.write_bytes(GIF)
        spec = self.spec()
        spec["sticker"].update(file=str(saved), missing_reason=None, preview=None)
        package = self.package([cp.prepare_sticker_record(spec, self.media)])
        archive = self.root / "base.zip"
        cp.create_zip(package, archive)
        delta = self.root / "delta"
        (delta / "media").mkdir(parents=True)
        manifest = copy.deepcopy(package.manifest)
        manifest.update(batch_id="synthetic-sticker-delta", base_batch_id=package.batch_id)
        manifest["attachments"][0]["source_batch_id"] = package.batch_id
        message = copy.deepcopy(package.messages[0])
        message["id"] = "delta-sticker"
        message["media"][0]["source_batch_id"] = package.batch_id
        (delta / "manifest.json").write_bytes(cp.encoded(manifest))
        (delta / "messages.jsonl").write_bytes(cp.encoded(message))
        loaded, batches = cp.load_bundle(delta, [archive])
        self.assertEqual(cp.sticker_visuals(loaded, batches)[0]["status"], "original_available")
        cp.require_sticker_visual(loaded, batches)
        with self.assertRaises(cp.Invalid):
            cp.require_sticker_visual(loaded)

    def test_invalid_specs_do_not_leave_staged_bytes(self):
        invalid_png = self.root / "bad.png"
        invalid_png.write_bytes(invented_png()[:-1])
        variants = []
        spec = self.spec()
        spec["sticker"]["preview"]["file"] = str(invalid_png)
        variants.append(spec)
        spec = self.spec()
        spec["sticker"]["preview"]["provenance"] = None
        variants.append(spec)
        spec = self.spec()
        spec["sticker"]["missing_reason"] = None
        variants.append(spec)
        spec = self.spec()
        spec["sticker"]["original_name"] = "x" * 2001
        variants.append(spec)
        spec = self.spec()
        spec["sticker"]["missing_reason"] = "x" * 4000
        variants.append(spec)
        spec = self.spec()
        spec["message"]["voice"] = {"transcripts": []}
        variants.append(spec)
        for spec in variants:
            with self.subTest(spec=spec), self.assertRaises(cp.Invalid):
                cp.prepare_sticker_record(spec, self.media)
            self.assertEqual(list(self.media.glob("*")), [])

    def test_duplicate_visible_stickers_remain_distinct_occurrences(self):
        records = [cp.prepare_sticker_record(self.spec(index), self.media) for index in range(2)]
        package = self.package(records)
        self.assertEqual(len(package.messages), 2)
        self.assertNotEqual(package.messages[0]["id"], package.messages[1]["id"])
        previews = [record["attachments"][1] for record in records]
        self.assertEqual(previews[0]["sha256"], previews[1]["sha256"])
        self.assertNotEqual(previews[0]["path"], previews[1]["path"])
        self.assertNotEqual(previews[0]["derived_from"], previews[1]["derived_from"])

    def test_sticker_cli_resolves_relative_crop_and_refuses_existing_output(self):
        spec = self.spec()
        spec["sticker"]["preview"]["file"] = self.crop.name
        path = self.root / "sticker.spec.json"
        path.write_bytes(cp.encoded(spec))
        output = self.root / "record.json"
        command = [sys.executable, str(SKILL / "scripts/chat_package.py"), "sticker-record", str(path),
                   "--media-dir", str(self.media), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("合成成员", result.stdout)
        self.assertEqual(cp.strict_json(result.stdout)["status"], "static_preview")
        record = cp.strict_json(output.read_bytes())
        self.package([record])
        before = set(self.media.iterdir())
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(set(self.media.iterdir()), before)

    def test_failed_staging_cleans_created_file(self):
        real_schema_check = cp.schema_check
        calls = 0
        def fail_final_message(value, schema, *args, **kwargs):
            nonlocal calls
            if type(value) is dict and value.get("type") == "sticker" and value.get("media"):
                calls += 1
                raise cp.Invalid("synthetic final validation failure")
            return real_schema_check(value, schema, *args, **kwargs)
        with patch.object(cp, "schema_check", fail_final_message), self.assertRaises(cp.Invalid):
            cp.prepare_sticker_record(self.spec(), self.media)
        self.assertEqual(calls, 1)
        self.assertEqual(list(self.media.glob("*")), [])

    def test_cli_output_failure_cleans_media_staged_for_that_record(self):
        spec = self.root / "sticker.spec.json"
        spec.write_bytes(cp.encoded(self.spec()))
        blocked = self.root / "blocked-parent"
        blocked.write_bytes(b"existing file")
        output = blocked / "record.json"
        result = subprocess.run([sys.executable, str(SKILL / "scripts/chat_package.py"), "sticker-record", str(spec),
                                 "--media-dir", str(self.media), "--output", str(output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(blocked.read_bytes(), b"existing file")
        self.assertFalse(output.exists())
        self.assertEqual(list(self.media.glob("*")), [])


if __name__ == "__main__":
    unittest.main()
