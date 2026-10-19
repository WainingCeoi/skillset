"""Observable invariants for offline synthetic WeCom capture packages."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "wecom-chat-capture"
sys.path.insert(0, str(SKILL / "scripts"))
import chat_package as cp
import make_synthetic


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixtures = make_synthetic.generate(self.root / "synthetic")
        self.baseline = self.fixtures / "baseline"
        self.delta = self.fixtures / "delta"

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, directory, manifest=None, messages=None):
        if manifest is not None:
            (directory / "manifest.json").write_bytes(cp.encoded(manifest))
        if messages is not None:
            (directory / "messages.jsonl").write_bytes(b"".join(cp.encoded(m) for m in messages))

    def loaded(self, directory=None):
        return cp.load_bundle(directory or self.baseline)[0]

    def test_mixed_baseline_and_delta_roundtrip_preserve_originals_and_media(self):
        baseline = self.loaded()
        self.assertEqual(len(baseline.messages), 8)
        self.assertEqual(baseline.messages[0]["text"], baseline.messages[1]["text"])
        self.assertNotEqual(baseline.messages[0]["id"], baseline.messages[1]["id"])
        self.assertIsNone(baseline.messages[7]["sent_at"])
        self.assertEqual(baseline.manifest["attachments"][1]["original_name"], "../原始显示名.txt")
        first, second = self.root / "first.zip", self.root / "second.zip"
        cp.create_zip(baseline, first)
        cp.create_zip(baseline, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        reread = self.loaded(first)
        self.assertEqual(reread.messages, baseline.messages)
        for name, data in baseline.entries.items():
            if name.startswith("media/"):
                self.assertEqual(reread.entries[name], data)
        delta, batches = cp.load_bundle(self.delta, [first])
        report = cp.preview(delta, batches)
        self.assertEqual(report["overlap_candidates"][0]["status"], "ambiguous")
        self.assertEqual(report["overlap_candidates"][0]["base_match_count"], 2)
        self.assertEqual(len(delta.messages), 3)  # preview did not merge anything
        cp.require_review(delta, self.fixtures / "delta-review.json")
        packed = self.root / "delta.zip"
        cp.create_zip(delta, packed)
        with zipfile.ZipFile(packed) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest.json", "messages.jsonl", "media/"})
        cp.load_bundle(packed, [first])

    def test_missing_original_is_explicit_and_preview_surfaces_unknowns(self):
        baseline, batches = cp.load_bundle(self.baseline)
        report = cp.preview(baseline, batches)
        self.assertEqual(report["missing_media"][0]["original_name"], "过期视频.mp4")
        self.assertEqual(report["unknown_times"], ["base-g7"])
        (self.baseline / "media/image.png").unlink()
        with self.assertRaisesRegex(cp.Invalid, "missing media bytes"):
            self.loaded()

    def test_hash_tamper_and_undeclared_extra_bytes_rejected(self):
        image = self.baseline / "media/image.png"
        original = image.read_bytes()
        image.write_bytes(b"changed")
        with self.assertRaisesRegex(cp.Invalid, "hash/size"):
            self.loaded()
        image.write_bytes(original)
        (self.baseline / "media/extra.bin").write_bytes(b"not declared")
        with self.assertRaisesRegex(cp.Invalid, "unlisted media"):
            self.loaded()

    def test_traversal_absolute_backslash_and_casefold_paths_rejected_before_read(self):
        for name in ("../escape", "/absolute", "media/../escape", "media/a\\b", "media//a", "media/%2e/a"):
            archive_path = self.root / "bad.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("manifest.json", b"{}")
                archive.writestr("messages.jsonl", b"{}\n")
                archive.writestr(name, b"untrusted")
            with self.subTest(name=name), self.assertRaises(cp.Invalid):
                cp.read_entries(archive_path)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("media/A.bin", b"a")
            archive.writestr("media/a.bin", b"b")
        with self.assertRaisesRegex(cp.Invalid, "casefold"):
            cp.read_entries(archive_path)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("media/bad0.bin", b"payload")
        # ZIP writers sanitize NULs, so mutate both stored filename occurrences.
        archive_path.write_bytes(archive_path.read_bytes().replace(b"media/bad0.bin", b"media/bad\0.bin"))
        with self.assertRaisesRegex(cp.Invalid, "NUL/aliased"):
            cp.read_entries(archive_path)
        self.assertFalse((self.root / "escape").exists())

    def test_symlinks_special_files_and_duplicate_zip_members_rejected(self):
        link = self.baseline / "media/link.bin"
        link.symlink_to(self.baseline / "media/image.png")
        with self.assertRaisesRegex(cp.Invalid, "symlink"):
            self.loaded()
        link.unlink()
        zip_path = self.root / "link.zip"
        info = zipfile.ZipInfo("media/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr(info, "../../elsewhere")
        with self.assertRaisesRegex(cp.Invalid, "symlink"):
            cp.read_entries(zip_path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("manifest.json", "{}")
        with self.assertRaisesRegex(cp.Invalid, "duplicate"):
            cp.read_entries(zip_path)

    def test_duplicate_batch_and_wrong_conversation_and_unresolved_base_rejected(self):
        with self.assertRaisesRegex(cp.Invalid, "duplicate batch"):
            cp.load_bundle(self.baseline, [self.baseline])
        with self.assertRaisesRegex(cp.Invalid, "unresolved base"):
            cp.load_bundle(self.delta)
        manifest = cp.strict_json((self.delta / "manifest.json").read_bytes())
        manifest["conversation_id"] = "other-conversation"
        self.rewrite(self.delta, manifest)
        with self.assertRaisesRegex(cp.Invalid, "conversation mismatch"):
            cp.load_bundle(self.delta, [self.baseline])

    def test_prior_media_must_match_explicit_batch_path_and_hash(self):
        manifest = cp.strict_json((self.delta / "manifest.json").read_bytes())
        messages = cp.message_lines((self.delta / "messages.jsonl").read_bytes())
        manifest["attachments"][0]["source_batch_id"] = "not-an-ancestor"
        messages[1]["media"][0]["source_batch_id"] = "not-an-ancestor"
        self.rewrite(self.delta, manifest, messages)
        with self.assertRaisesRegex(cp.Invalid, "declared ancestor"):
            cp.load_bundle(self.delta, [self.baseline])
        manifest["attachments"][0]["source_batch_id"] = "synthetic-baseline-001"
        messages[1]["media"][0]["source_batch_id"] = "synthetic-baseline-001"
        manifest["attachments"][0]["sha256"] = "0" * 64
        messages[1]["media"][0]["sha256"] = "0" * 64
        self.rewrite(self.delta, manifest, messages)
        with self.assertRaisesRegex(cp.Invalid, "prior media identity"):
            cp.load_bundle(self.delta, [self.baseline])

    def test_overlap_requires_review_evidence_and_originals_are_checked(self):
        delta, _ = cp.load_bundle(self.delta, [self.baseline])
        with self.assertRaisesRegex(cp.Invalid, "explicit --review"):
            cp.require_review(delta, None)
        review = cp.strict_json((self.fixtures / "delta-review.json").read_bytes())
        review["decisions"][0]["base_message_id"] = "base-g0"
        bad_review = self.root / "review.json"
        bad_review.write_bytes(cp.encoded(review))
        with self.assertRaisesRegex(cp.Invalid, "exact anchor"):
            cp.require_review(delta, bad_review)
        messages = delta.messages
        messages[0]["text"] = "different originals"
        self.rewrite(self.delta, messages=messages)
        with self.assertRaisesRegex(cp.Invalid, "overlap originals"):
            cp.load_bundle(self.delta, [self.baseline])

    def test_normalize_is_deterministic_and_does_not_merge_or_infer_times(self):
        baseline = self.loaded()
        baseline.messages[0]["id"] = None
        baseline.messages[1]["id"] = None
        # Assign IDs before resolving replies; an old ID must not be guessed onto
        # a newly generated observation. Keep the visible quote as original text.
        baseline.messages[5]["reply_to"] = None
        baseline.manifest["counts"]["messages"] = 123
        baseline.manifest["attachments"][0]["sha256"] = None
        baseline.manifest["attachments"][0]["size_bytes"] = None
        self.rewrite(self.baseline, baseline.manifest, baseline.messages)
        first, second = self.root / "normalized-1", self.root / "normalized-2"
        cp.normalize(self.baseline, first, [])
        cp.normalize(self.baseline, second, [])
        one, two = self.loaded(first), self.loaded(second)
        self.assertEqual(one.entries, two.entries)
        self.assertNotEqual(one.messages[0]["id"], one.messages[1]["id"])
        self.assertTrue(one.messages[0]["id"].startswith("g-"))
        self.assertEqual(len(one.messages), 8)
        self.assertIsNone(one.messages[7]["sent_at"])
        self.assertEqual(one.messages[0]["text"], "收到 ✅\n原文保留")
        self.assertEqual(one.entries["media/image.png"], baseline.entries["media/image.png"])

    def test_unicode_line_separators_are_original_content_not_record_boundaries(self):
        baseline = self.loaded()
        baseline.messages[0]["text"] = "line\u2028paragraph\u2029separator\r\n中文"
        self.rewrite(self.baseline, messages=baseline.messages)
        self.assertEqual(self.loaded().messages[0]["text"], baseline.messages[0]["text"])

    def test_schema_identity_time_counts_order_and_reply_invariants(self):
        baseline = self.loaded()
        mutations = [lambda p: p.manifest.update(version="wrong"),
                     lambda p: p.manifest.update(extra="forbidden"),
                     lambda p: p.manifest["counts"].update(messages=999),
                     lambda p: p.manifest["capture"].update(timezone="Not/AZone"),
                     lambda p: p.messages[0].update(sent_at="2026-10-19T10:00:00"),
                     lambda p: p.messages[0].update(source_id="made-up-stable-id"),
                     lambda p: p.messages[1].update(id=p.messages[0]["id"]),
                     lambda p: p.messages[1].update(order=p.messages[0]["order"]),
                     lambda p: p.messages[1]["sender"].update(is_self=0),
                     lambda p: p.messages[5]["reply_to"].update(message_id="absent")]
        for mutate in mutations:
            package = copy.deepcopy(baseline)
            mutate(package)
            self.rewrite(self.baseline, package.manifest, package.messages)
            with self.subTest(mutate=mutate), self.assertRaises((cp.Invalid, ValueError, KeyError)):
                self.loaded()

    def test_stage_media_preserves_bytes_names_and_separate_same_byte_occurrences(self):
        source = self.baseline / "media/notes.txt"
        media = self.root / "staging/media"
        first = cp.stage_media(source, media, "../../显示名.txt", "text/plain")
        second = cp.stage_media(source, media, "另一个名字.txt", "text/plain")
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(first["original_name"], "../../显示名.txt")
        self.assertEqual((media.parent / first["path"]).read_bytes(), source.read_bytes())

    def test_failed_pack_and_normalize_preserve_existing_outputs(self):
        existing = self.root / "keep.zip"
        existing.write_bytes(b"unchanged")
        with self.assertRaisesRegex(cp.Invalid, "overwrite"):
            cp.create_zip(self.loaded(), existing)
        self.assertEqual(existing.read_bytes(), b"unchanged")
        with self.assertRaisesRegex(cp.Invalid, "already exists"):
            cp.normalize(self.baseline, self.baseline, [])
        self.assertEqual(list(self.root.glob(".chat-*")), [])

    def test_cli_end_to_end_and_checked_in_fixture_reproducibility(self):
        output = self.root / "cli.zip"
        result = subprocess.run([sys.executable, str(SKILL / "scripts/chat_package.py"), "pack",
                                 str(self.baseline), "--output", str(output)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["zip_sha256"], cp.digest(output.read_bytes()))
        for generated in self.fixtures.rglob("*"):
            if generated.is_file():
                checked_in = SKILL / "assets/synthetic" / generated.relative_to(self.fixtures)
                self.assertEqual(generated.read_bytes(), checked_in.read_bytes())

    def test_checkpoint_resume_scope_and_prefix_checks_preserve_verified_observations(self):
        package, batches = cp.load_bundle(self.baseline)
        state = self.root / "checkpoint-001.json"
        result = cp.checkpoint(package, batches, state, "viewport:1 / last message base-g7",
                               "Synthetic scope authorization, no real UI capture")
        self.assertEqual(result["preview"]["missing_media"][0]["path"], "media/unavailable-video.bin")
        self.assertEqual(cp.resume_check(package, batches, state)["verified_prefix_messages"], 8)
        changed = copy.deepcopy(package)
        changed.manifest["conversation_id"] = "wrong-conversation"
        with self.assertRaisesRegex(cp.Invalid, "resume scope mismatch"):
            cp.resume_check(changed, batches, state)
        changed = copy.deepcopy(package)
        changed.messages[0]["text"] = "changed original"
        with self.assertRaisesRegex(cp.Invalid, "prefix changed"):
            cp.resume_check(changed, batches, state)
        with self.assertRaises(FileExistsError):
            cp.checkpoint(package, batches, state, "cursor", "scope")

    def test_resource_limits_and_self_replies_fail_without_partial_output(self):
        output = self.root / "too-large.zip"
        with patch.object(cp, "MAX_ZIP", 1), self.assertRaisesRegex(cp.Invalid, "upload limit"):
            cp.create_zip(self.loaded(), output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".chat-package-*")), [])
        with patch.object(cp, "MAX_LINE", 4), self.assertRaisesRegex(cp.Invalid, "line exceeds"):
            cp.message_lines(b'{"text":"large"}\n')
        package = self.loaded()
        package.messages[0]["reply_to"] = {"batch_id": package.batch_id, "message_id": package.messages[0]["id"]}
        self.rewrite(self.baseline, messages=package.messages)
        with self.assertRaisesRegex(cp.Invalid, "self reply"):
            self.loaded()


if __name__ == "__main__":
    unittest.main()
