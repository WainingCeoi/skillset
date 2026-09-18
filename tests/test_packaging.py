"""Behavioral tests for the repository's .skill packager."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGER = REPO_ROOT / "scripts" / "package_skills.py"


class PackageSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        skill = self.root / "skills" / "example-skill"
        (skill / "assets").mkdir(parents=True)
        (skill / "references").mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: example-skill\ndescription: Example.\n---\n", encoding="utf-8"
        )
        (skill / "assets" / "template.txt").write_text("template\n", encoding="utf-8")
        (skill / "references" / "guide.md").write_text("guide\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_packager(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(PACKAGER), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_build_is_repeatable_and_contains_the_complete_skill_tree(self) -> None:
        first = self.run_packager("build")
        self.assertEqual(first.returncode, 0, first.stderr)
        bundle = self.root / "example-skill.skill"
        first_bytes = bundle.read_bytes()

        with zipfile.ZipFile(bundle) as archive:
            self.assertEqual(
                archive.namelist(),
                [
                    "example-skill/",
                    "example-skill/SKILL.md",
                    "example-skill/assets/",
                    "example-skill/assets/template.txt",
                    "example-skill/references/",
                    "example-skill/references/guide.md",
                ],
            )
            self.assertEqual(archive.read("example-skill/assets/template.txt"), b"template\n")

        second = self.run_packager("build")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(bundle.read_bytes(), first_bytes)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not portable")
    def test_build_creates_a_world_readable_bundle(self) -> None:
        built = self.run_packager("build")
        self.assertEqual(built.returncode, 0, built.stderr)
        bundle = self.root / "example-skill.skill"
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o644)

    def test_check_rejects_missing_stale_and_unexpected_bundle_entries(self) -> None:
        self.assertEqual(self.run_packager("build").returncode, 0)
        self.assertEqual(self.run_packager("--check").returncode, 0)
        bundle = self.root / "example-skill.skill"

        bundle.unlink()
        missing = self.run_packager("--check")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing bundle", missing.stderr)

        self.assertEqual(self.run_packager("build").returncode, 0)
        (self.root / "skills" / "example-skill" / "SKILL.md").write_text(
            "---\nname: example-skill\ndescription: Changed.\n---\n", encoding="utf-8"
        )
        stale = self.run_packager("--check")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("content differs", stale.stderr)

        self.assertEqual(self.run_packager("build").returncode, 0)
        with zipfile.ZipFile(bundle, "a") as archive:
            archive.writestr("example-skill/unexpected.txt", "nope")
        unexpected = self.run_packager("--check")
        self.assertNotEqual(unexpected.returncode, 0)
        self.assertIn("unexpected entries", unexpected.stderr)

    def test_check_rejects_duplicate_bundle_entries(self) -> None:
        self.assertEqual(self.run_packager("build").returncode, 0)
        bundle = self.root / "example-skill.skill"
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Duplicate name:.*", category=UserWarning)
            with zipfile.ZipFile(bundle, "a") as archive:
                archive.writestr("example-skill/assets/template.txt", "template\n")

        duplicate = self.run_packager("--check")
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("duplicate entries", duplicate.stderr)

    def test_build_excludes_standard_generated_cruft(self) -> None:
        skill = self.root / "skills" / "example-skill"
        (skill / "__pycache__").mkdir()
        (skill / "__pycache__" / "module.pyc").write_bytes(b"cache")
        (skill / ".DS_Store").write_bytes(b"finder")
        (skill / "assets" / "module.pyc").write_bytes(b"cache")
        (skill / "assets" / "module.pyo").write_bytes(b"cache")

        built = self.run_packager("build")
        self.assertEqual(built.returncode, 0, built.stderr)
        with zipfile.ZipFile(self.root / "example-skill.skill") as archive:
            self.assertEqual(
                archive.namelist(),
                [
                    "example-skill/",
                    "example-skill/SKILL.md",
                    "example-skill/assets/",
                    "example-skill/assets/template.txt",
                    "example-skill/references/",
                    "example-skill/references/guide.md",
                ],
            )

    def test_build_rejects_a_symlinked_directory(self) -> None:
        external = self.root / "outside"
        external.mkdir()
        (external / "secret.txt").write_text("outside\n", encoding="utf-8")
        (self.root / "skills" / "example-skill" / "linked").symlink_to(
            external, target_is_directory=True
        )

        built = self.run_packager("build")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("symlink", built.stderr)

    def test_build_rejects_an_output_symlink_without_changing_its_target(self) -> None:
        bundle = self.root / "example-skill.skill"
        target = self.root / "unrelated.txt"
        target.write_text("keep this file\n", encoding="utf-8")
        bundle.symlink_to(target)

        built = self.run_packager("build")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("output bundle is a symlink", built.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep this file\n")
        self.assertTrue(bundle.is_symlink())

    def test_check_rejects_an_output_symlink_without_reading_its_target(self) -> None:
        bundle = self.root / "example-skill.skill"
        target = self.root / "unrelated.txt"
        target.write_text("not a bundle\n", encoding="utf-8")
        bundle.symlink_to(target)

        checked = self.run_packager("--check")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("output bundle is a symlink", checked.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "not a bundle\n")

    def test_failed_build_preserves_existing_bundle_without_temp_debris(self) -> None:
        self.assertEqual(self.run_packager("build").returncode, 0)
        bundle = self.root / "example-skill.skill"
        original = bundle.read_bytes()
        external = self.root / "outside"
        external.mkdir()
        (self.root / "skills" / "example-skill" / "linked").symlink_to(
            external, target_is_directory=True
        )

        failed = self.run_packager("build")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("symlink", failed.stderr)
        self.assertEqual(bundle.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".example-skill.skill.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
