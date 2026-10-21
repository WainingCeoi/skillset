"""Offline visual QA renders retained bytes without interpreting message content."""
from __future__ import annotations

import base64
from html.parser import HTMLParser
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/wecom-chat-capture"
sys.path.insert(0, str(SKILL / "scripts"))
import chat_package as cp
import make_synthetic
import make_voice_synthetic
import review_chat


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixtures = make_voice_synthetic.generate(self.root / "fixtures")
        self.baseline = self.fixtures / "baseline"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, package, directory=None):
        directory = directory or self.baseline
        (directory / "manifest.json").write_bytes(cp.encoded(package.manifest))
        (directory / "messages.jsonl").write_bytes(b"".join(cp.encoded(message) for message in package.messages))

    def test_missing_sticker_renders_real_static_crop_and_transcript_stays_separate(self):
        package, _ = cp.load_bundle(self.baseline)
        zip_path = self.root / "capture.zip"
        cp.create_zip(package, zip_path)
        output = self.root / "review.html"
        review_chat.render(zip_path, output)
        html = output.read_text()
        elements = Elements(html).elements
        images = [attrs for tag, attrs in elements if tag == "img"]
        self.assertEqual(len(images), 1)
        self.assertEqual(base64.b64decode(images[0]["src"].split(",", 1)[1]),
                         (self.fixtures / "synthetic-preview.png").read_bytes())
        self.assertIn("Static screenshot fallback · original unavailable", html)
        self.assertIn("Original attachments: partial", html)
        self.assertIn("WeCom UI transcription · derived", html)
        self.assertIn("这是合成的界面转写示例。", html)
        self.assertEqual([attrs["data-message-id"] for tag, attrs in elements if tag == "article"],
                         [message["id"] for message in package.messages])
        self.assertNotIn("script", [tag for tag, _ in elements])
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_escape_text_sender_title_filename_and_deny_active_media(self):
        package, _ = cp.load_bundle(self.baseline)
        package.manifest["title"] = '<script src="https://example.invalid"></script>'
        package.messages[0]["sender"]["name"] = '<img src=x onerror="alert(1)">'
        package.messages[0]["text"] = '<iframe src="https://example.invalid"></iframe>\n& original text'
        path = package.manifest["attachments"][0]["path"]
        (self.baseline / path).write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        item = package.manifest["attachments"][0]
        item.update(content_type="image/svg+xml", original_name='<script>alert(2)</script>',
                    sha256=cp.digest((self.baseline / path).read_bytes()), size_bytes=(self.baseline / path).stat().st_size)
        package.messages[0]["media"][0]["sha256"] = item["sha256"]
        # The first occurrence is intentionally changed to an unsupported generic media type.
        package.messages[0].update(type="image", voice=None)
        self.write(package)
        output = self.root / "escaped.html"
        review_chat.render(self.baseline, output)
        html = output.read_text()
        tags = [tag for tag, _ in Elements(html).elements]
        self.assertNotIn("script", tags)
        self.assertNotIn("iframe", tags)
        self.assertNotIn("svg", tags)
        self.assertIn('&lt;iframe src=&quot;https://example.invalid&quot;&gt;', html)
        self.assertIn('&amp; original text', html)
        self.assertIn('&lt;script&gt;alert(2)&lt;/script&gt;', html)
        self.assertNotIn("data:image/svg+xml", html)

    def test_animated_original_is_embedded_unchanged_and_prior_media_resolves(self):
        fixtures = make_synthetic.generate(self.root / "mixed")
        base, _ = cp.load_bundle(fixtures / "baseline")
        gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
               b"!\xf9\x04\x00\x04\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00"
               b"!\xf9\x04\x00\x09\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00;")
        item = base.manifest["attachments"][0]
        path = item["path"]
        (fixtures / "baseline" / path).write_bytes(gif)
        item.update(sha256=cp.digest(gif), size_bytes=len(gif), content_type="image/gif")
        base.messages[2]["media"][0]["sha256"] = item["sha256"]
        self.write(base, fixtures / "baseline")
        # Update the explicit ancestor reference to the deliberately changed fixture bytes.
        manifest = cp.strict_json((fixtures / "delta/manifest.json").read_bytes())
        messages = cp.message_lines((fixtures / "delta/messages.jsonl").read_bytes())
        manifest["attachments"][0].update(sha256=item["sha256"], size_bytes=len(gif), content_type="image/gif")
        messages[1]["media"][0]["sha256"] = item["sha256"]
        (fixtures / "delta/manifest.json").write_bytes(cp.encoded(manifest))
        (fixtures / "delta/messages.jsonl").write_bytes(b"".join(cp.encoded(message) for message in messages))
        output = self.root / "prior.html"
        review_chat.render(fixtures / "delta", output, [fixtures / "baseline"])
        images = [attrs for tag, attrs in Elements(output.read_text()).elements if tag == "img"]
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0]["src"].startswith("data:image/gif;base64,"))
        self.assertEqual(base64.b64decode(images[0]["src"].split(",", 1)[1]), gif)

    def test_invalid_input_existing_output_output_inside_package_and_limits_leave_no_artifact(self):
        output = self.root / "output.html"
        output.write_bytes(b"keep")
        with self.assertRaisesRegex(cp.Invalid, "overwrite"):
            review_chat.render(self.baseline, output)
        self.assertEqual(output.read_bytes(), b"keep")
        inside = self.baseline / "review.html"
        with self.assertRaisesRegex(cp.Invalid, "outside"):
            review_chat.render(self.baseline, inside)
        self.assertFalse(inside.exists())
        output.unlink()
        with patch.object(review_chat, "MAX_HTML_BYTES", 1), self.assertRaisesRegex(cp.Invalid, "128 MiB"):
            review_chat.render(self.baseline, output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".chat-review-*")), [])
        (self.baseline / "manifest.json").write_bytes(b"invalid")
        with self.assertRaises(ValueError):
            review_chat.render(self.baseline, output)
        self.assertFalse(output.exists())

    def test_cli_reports_only_output_metadata_and_mime_mismatch_is_not_embedded(self):
        self.assertFalse(review_chat.image_matches(b"<html>active content</html>", "image/png"))
        output = self.root / "cli.html"
        result = subprocess.run([sys.executable, str(SKILL / "scripts/review_chat.py"), str(self.baseline),
                                 "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("这是合成", result.stdout)
        self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
