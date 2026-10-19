"""Synthetic voice and explicitly derived static preview contract checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path
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
import make_voice_synthetic as synthetic


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixtures = synthetic.generate(self.root / "fixtures")
        self.package = cp.load_bundle(self.fixtures / "baseline")[0]

    def tearDown(self):
        self.temp.cleanup()

    def altered(self, change):
        package = copy.deepcopy(self.package)
        change(package)
        package.entries["manifest.json"] = cp.encoded(package.manifest)
        package.entries["messages.jsonl"] = b"".join(cp.encoded(m) for m in package.messages)
        return cp.parse_entries(package.entries)

    def test_audio_unchanged_transcript_separate_and_missing_occurrences_retained(self):
        first, transcribed, missing, sticker = self.package.messages
        path = first["media"][0]["path"]
        self.assertEqual(self.package.entries[path], (self.fixtures / "synthetic-original.wav").read_bytes())
        self.assertEqual(first["voice"]["duration_ms"], 1000)
        self.assertIsNone(transcribed["text"])
        self.assertEqual(transcribed["voice"]["transcripts"][0]["source"], "wecom_ui")
        self.assertEqual(missing["voice"], {"original_duration": '7″', "duration_ms": None, "transcripts": []})
        self.assertEqual(missing["sender"]["name"], "合成语音成员")
        self.assertEqual(missing["original_time"], "10/19 9:30")
        self.assertIsNone(missing["sent_at"])
        self.assertEqual(missing["order"], 2)
        report = cp.preview(self.package, {})
        self.assertEqual(len(report["missing_media"]), 3)
        self.assertEqual(len(report["derived_previews"]), 1)
        self.assertEqual(len(report["voice_messages"]), 3)
        self.assertEqual(report["voice_messages"][1]["ui_transcripts"], 1)
        self.assertNotIn("这是合成", json.dumps(report, ensure_ascii=False))
        archive = self.root / "voice.zip"
        cp.create_zip(self.package, archive)
        self.assertEqual(cp.load_bundle(archive)[0].messages, self.package.messages)
        normalized = self.root / "normalized"
        cp.normalize(self.fixtures / "baseline", normalized, [])
        self.assertEqual(cp.load_bundle(normalized)[0].messages, self.package.messages)

    def test_invalid_voice_type_text_transcript_source_audio_and_duration_rejected(self):
        changes = [
            lambda p: p.messages[0].update(type="text"),
            lambda p: p.messages[1].update(text="mistaken original transcript"),
            lambda p: p.messages[1]["voice"]["transcripts"][0].update(source="guessed"),
            lambda p: p.manifest["attachments"][0].update(content_type="application/octet-stream"),
            lambda p: p.messages[0]["voice"].update(duration_ms=-1),
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(cp.Invalid):
                self.altered(change)

    def test_derived_preview_requires_missing_original_provenance_and_same_message(self):
        changes = [
            lambda p: p.manifest["attachments"][-1].update(provenance=None),
            lambda p: p.manifest["attachments"][-1].update(derived_from="media/not-present.gif"),
            lambda p: p.messages[-1]["media"].pop(0),
            lambda p: p.messages[-1]["media"][-1].update(role="original"),
            lambda p: p.manifest["completeness"].update(attachments="complete"),
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(cp.Invalid):
                self.altered(change)
        original = self.package.manifest["attachments"][-2]
        self.assertEqual(original["completeness"], "missing")
        self.assertNotIn(original["path"], self.package.entries)

    def test_fingerprint_ignores_derived_content_but_preserves_duration_and_reply(self):
        voice = copy.deepcopy(self.package.messages[1])
        expected = cp.original_fingerprint(voice)
        voice["voice"]["transcripts"][0]["text"] = "另一个合成转写"
        voice["provenance"]["notes"] = "different locator evidence"
        self.assertEqual(expected, cp.original_fingerprint(voice))
        voice["voice"]["duration_ms"] = 13000
        self.assertNotEqual(expected, cp.original_fingerprint(voice))
        sticker = copy.deepcopy(self.package.messages[-1])
        expected = cp.original_fingerprint(sticker)
        sticker["media"][-1]["sha256"] = "f" * 64
        self.assertEqual(expected, cp.original_fingerprint(sticker))
        sticker["reply_to"] = {"message_id": "other", "batch_id": "other-batch"}
        self.assertNotEqual(expected, cp.original_fingerprint(sticker))

    def test_unique_missing_original_overlap_always_reports_review(self):
        incoming = copy.deepcopy(self.package)
        incoming.manifest["base_batch_id"] = self.package.batch_id
        incoming.manifest["batch_id"] = "new-synthetic-batch"
        for message in incoming.messages:
            message["id"] += "-incoming"
        report = cp.preview(incoming, {self.package.batch_id: self.package})
        self.assertEqual([c["status"] for c in report["overlap_candidates"]],
                         ["candidate_only", "incomplete_original", "incomplete_original", "incomplete_original"])

    def test_png_rejects_animation_corruption_truncation_trailing_and_bounds(self):
        png = synthetic.invented_png()
        self.assertEqual(cp.static_png_size(png), (16, 16))
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        # Even an APNG declaring just one frame is forbidden for screenshot previews.
        animated = png[:33] + chunk(b"acTL", struct.pack(">II", 1, 0)) + png[33:]
        corrupt = png[:45] + bytes([png[45] ^ 1]) + png[46:]
        oversized = png[:8] + chunk(b"IHDR", struct.pack(">IIBBBBB", 16385, 1, 8, 2, 0, 0, 0)) + png[33:]
        for value in (animated, corrupt, png[:-1], png + b"extra", oversized):
            with self.subTest(size=len(value)), self.assertRaises(cp.Invalid):
                cp.static_png_size(value)
        with patch.object(cp, "MAX_PREVIEW_PIXELS", 255), self.assertRaises(cp.Invalid):
            cp.static_png_size(png)

    def test_aggregate_preview_budget_is_checked_across_images(self):
        def add_preview(package):
            item = copy.deepcopy(package.manifest["attachments"][-1])
            item["path"] = "media/second-preview.png"
            package.entries[item["path"]] = package.entries[package.manifest["attachments"][-1]["path"]]
            package.manifest["attachments"].append(item)
            package.manifest["counts"]["attachments"] += 1
            package.messages[-1]["media"].append({k: item[k] for k in ("path", "sha256", "source_batch_id", "role")})
        with patch.object(cp, "MAX_PREVIEW_PIXELS", 300), self.assertRaisesRegex(cp.Invalid, "aggregate"):
            self.altered(add_preview)

    def test_voice_record_cli_resolves_relative_audio_and_does_not_print_transcript(self):
        for name in ("voice-original", "voice-transcript-only", "voice-missing-both"):
            output = self.root / (name + ".json")
            command = [sys.executable, str(SKILL / "scripts/chat_package.py"), "voice-record",
                       str(self.fixtures / (name + ".spec.json")), "--media-dir", str(self.root / "staged"),
                       "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("这是合成", result.stdout)
            record = cp.strict_json(output.read_bytes())
            self.assertEqual(record["message"]["type"], "voice")
            if name == "voice-original":
                self.assertEqual((self.root / "staged" / Path(record["attachment"]["path"]).name).read_bytes(),
                                 (self.fixtures / "synthetic-original.wav").read_bytes())
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_checked_in_examples_reproduce_exactly(self):
        checked = SKILL / "assets/synthetic-voice-stickers"
        for path in self.fixtures.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (checked / path.relative_to(self.fixtures)).read_bytes())


if __name__ == "__main__":
    unittest.main()
