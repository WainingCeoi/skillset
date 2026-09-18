import builtins
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fitz


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "skills/translate-documents/assets/overlay_translate.py"
OVERLAY_SPEC = importlib.util.spec_from_file_location("overlay_translate_for_test", OVERLAY)
OVERLAY_MODULE = importlib.util.module_from_spec(OVERLAY_SPEC)
OVERLAY_SPEC.loader.exec_module(OVERLAY_MODULE)


class OverlayTranslateRasterTests(unittest.TestCase):
    def test_gray_alpha_png_preserves_untouched_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            output = tmp_path / "translated.png"
            spec = tmp_path / "spec.json"

            image = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 400, 200), True)
            image.set_alpha(bytes(image.width * image.height), premultiply=False)
            image.set_pixel(20, 20, (50, 127))
            image.save(source)
            source_pixels = fitz.Pixmap(source)
            spec.write_text(json.dumps({
                "dpi": 144,
                "labels": [{
                    "id": 1,
                    "page": 0,
                    "bbox": [100, 50, 160, 40],
                    "en": "Translated",
                    "style": "white",
                }],
            }))

            result = subprocess.run(
                [sys.executable, str(OVERLAY), str(spec), str(source), str(output), "--mode", "en"],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = fitz.Pixmap(output)
            self.assertEqual(rendered.colorspace.name, "DeviceGray")
            self.assertEqual(rendered.pixel(20, 20), source_pixels.pixel(20, 20))

    def test_png_input_preserves_untouched_transparency(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            output = tmp_path / "translated.png"
            spec = tmp_path / "spec.json"

            image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 200), True)
            image.set_alpha(bytes(image.width * image.height), premultiply=False)
            image.set_pixel(20, 20, (17, 34, 51, 127))
            self.assertEqual(image.pixel(0, 0)[3], 0)
            image.save(source)
            source_pixels = fitz.Pixmap(source)
            spec.write_text(json.dumps({
                "dpi": 144,
                "labels": [{
                    "id": 1,
                    "page": 0,
                    "bbox": [100, 50, 160, 40],
                    "en": "Translated",
                    "style": "white",
                }],
            }))

            result = subprocess.run(
                [sys.executable, str(OVERLAY), str(spec), str(source), str(output), "--mode", "en"],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = fitz.Pixmap(output)
            self.assertTrue(rendered.alpha)
            self.assertEqual(rendered.pixel(0, 0), source_pixels.pixel(0, 0))
            self.assertEqual(rendered.pixel(20, 20), source_pixels.pixel(20, 20))

    def test_spec_is_read_as_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.pdf"
            output = tmp_path / "translated.pdf"
            spec = tmp_path / "spec.json"

            document = fitz.open()
            document.new_page(width=612, height=792)
            document.save(source)
            spec.write_text(json.dumps({
                "dpi": 72,
                "labels": [{
                    "id": 1,
                    "page": 0,
                    "bbox": [68, 55, 80, 25],
                    "en": "Hello",
                    "zh": "中文",
                    "he": "שלום",
                    "style": "white",
                }],
            }, ensure_ascii=False), encoding="utf-8")

            real_open = builtins.open

            def require_utf8(path, *args, **kwargs):
                if Path(path) == spec:
                    self.assertEqual(kwargs.get("encoding"), "utf-8")
                return real_open(path, *args, **kwargs)

            with mock.patch.object(sys, "argv", [str(OVERLAY), str(spec), str(source), str(output)]), \
                 mock.patch("builtins.open", side_effect=require_utf8):
                OVERLAY_MODULE.main()

            self.assertTrue(output.exists())

    def test_png_input_overlays_target_and_preserves_untouched_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            output = tmp_path / "translated.png"
            spec = tmp_path / "spec.json"

            image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 200), False)
            image.clear_with(255)
            image.set_pixel(20, 20, (17, 34, 51))
            for y in range(60, 80):
                for x in range(120, 240):
                    image.set_pixel(x, y, (0, 0, 0))
            image.save(source)
            spec.write_text(json.dumps({
                "dpi": 144,
                "labels": [{
                    "id": 1,
                    "page": 0,
                    "bbox": [100, 50, 160, 40],
                    "en": "Translated",
                    "style": "white",
                }],
            }))

            result = subprocess.run(
                [sys.executable, str(OVERLAY), str(spec), str(source), str(output), "--mode", "en"],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = fitz.Pixmap(output)
            self.assertEqual((rendered.width, rendered.height), (400, 200))
            self.assertEqual(rendered.pixel(20, 20), image.pixel(20, 20))
            self.assertEqual(rendered.pixel(125, 60), (255, 255, 255))
            self.assertTrue(any(
                rendered.pixel(x, y) != (255, 255, 255)
                for y in range(50, 90)
                for x in range(100, 260)
            ))

    def test_jpeg_input_writes_same_size_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.jpg"
            output = tmp_path / "translated.jpg"
            spec = tmp_path / "spec.json"

            image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 320, 180), False)
            image.clear_with(255)
            image.save(source)
            spec.write_text(json.dumps({
                "dpi": 144,
                "labels": [{
                    "id": 1,
                    "page": 0,
                    "bbox": [30, 20, 100, 25],
                    "en": "English",
                    "style": "white",
                }],
            }))

            result = subprocess.run(
                [sys.executable, str(OVERLAY), str(spec), str(source), str(output), "--mode", "en"],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = fitz.Pixmap(output)
            self.assertEqual((rendered.width, rendered.height), (320, 180))
            self.assertFalse(rendered.alpha)

    def test_pdf_input_writes_single_page_pdf_with_replacement_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.pdf"
            output = tmp_path / "translated.pdf"
            spec = tmp_path / "spec.json"

            document = fitz.open()
            document.new_page(width=612, height=792).insert_text((72, 72), "SOURCE")
            document.save(source)
            spec.write_text(json.dumps({
                "dpi": 72,
                "labels": [{
                    "id": 1,
                    "page": 0,
                    "bbox": [68, 55, 80, 25],
                    "en": "Hello",
                    "style": "white",
                }],
            }))

            result = subprocess.run(
                [sys.executable, str(OVERLAY), str(spec), str(source), str(output), "--mode", "en"],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            translated = fitz.open(output)
            self.assertTrue(translated.is_pdf)
            self.assertEqual(translated.page_count, 1)
            self.assertIn("Hello", translated[0].get_text())


if __name__ == "__main__":
    unittest.main()
