#!/usr/bin/env python3
"""Build and verify deterministic .skill ZIP bundles from skills/<name>."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path


FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def skill_directories(root: Path) -> list[Path]:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        raise ValueError(f"missing skills directory: {skills_root}")
    children = sorted(skills_root.iterdir())
    symlinks = [path for path in children if path.is_symlink()]
    if symlinks:
        raise ValueError(f"symlinks are not supported: {symlinks[0]}")
    skills = [path for path in children if path.is_dir() and (path / "SKILL.md").is_file()]
    if not skills:
        raise ValueError(f"no skills found in {skills_root}")
    return skills


def archive_entries(skill: Path) -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = [(f"{skill.name}/", b"")]

    def visit(directory: Path) -> None:
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if path.is_symlink():
                raise ValueError(f"symlinks are not supported: {path}")
            if path.name == "__pycache__" or path.name == ".DS_Store" or path.suffix in {".pyc", ".pyo"}:
                continue
            relative = path.relative_to(skill).as_posix()
            name = f"{skill.name}/{relative}"
            if path.is_dir():
                entries.append((f"{name}/", b""))
                visit(path)
            elif path.is_file():
                entries.append((name, path.read_bytes()))

    visit(skill)
    return entries


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
    info.create_system = 3
    info.external_attr = ((0o40755 if name.endswith("/") else 0o100644) << 16)
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def write_bundle(bundle: Path, entries: list[tuple[str, bytes]]) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{bundle.name}.", suffix=".tmp", dir=bundle.parent
    )
    os.close(descriptor)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in entries:
                archive.writestr(zip_info(name), content)
        os.chmod(temp, 0o644)
        os.replace(temp, bundle)
    finally:
        temp.unlink(missing_ok=True)


def build(root: Path) -> None:
    sources = [(skill, archive_entries(skill)) for skill in skill_directories(root)]
    bundles = [(skill, entries, root / f"{skill.name}.skill") for skill, entries in sources]
    for _, _, bundle in bundles:
        if bundle.is_symlink():
            raise ValueError(f"output bundle is a symlink: {bundle}")
    for skill, entries, bundle in bundles:
        write_bundle(bundle, entries)
        print(f"built {bundle.relative_to(root)}")


def check_bundle(root: Path, skill: Path) -> list[str]:
    bundle = root / f"{skill.name}.skill"
    if bundle.is_symlink():
        return [f"{skill.name}: output bundle is a symlink: {bundle.name}"]
    if not bundle.is_file():
        return [f"{skill.name}: missing bundle {bundle.name}"]

    expected = dict(archive_entries(skill))
    try:
        with zipfile.ZipFile(bundle) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted(name for name, count in Counter(names).items() if count > 1)
            actual_names = set(names)
            missing = sorted(set(expected) - actual_names)
            unexpected = sorted(actual_names - set(expected))
            errors: list[str] = []
            if missing:
                errors.append(f"{skill.name}: missing entries: {', '.join(missing)}")
            if unexpected:
                errors.append(f"{skill.name}: unexpected entries: {', '.join(unexpected)}")
            if duplicate_names:
                errors.append(f"{skill.name}: duplicate entries: {', '.join(duplicate_names)}")
            for name in sorted(set(expected) & actual_names):
                if archive.read(name) != expected[name]:
                    errors.append(f"{skill.name}: content differs: {name}")
            return errors
    except zipfile.BadZipFile:
        return [f"{skill.name}: invalid bundle {bundle.name}"]


def check(root: Path) -> int:
    errors = [error for skill in skill_directories(root) for error in check_bundle(root, skill)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("all skill bundles match source")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("build",), default="build")
    parser.add_argument("--check", action="store_true", help="fail when bundles differ from source")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.check:
            return check(root)
        build(root)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
