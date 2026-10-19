#!/usr/bin/env python3
"""Offline WeCom capture normalization, preview, and deterministic Slinx v1 ZIPs.

No UI, network, OCR, transcription, or upload code. Python 3.10+ standard library.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile
import zipfile
import zlib
from zoneinfo import ZoneInfo


VERSION = "slinx-chat-zip-v1"
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_ZIP = 32 * 1024 * 1024
MAX_LINE = 1024 * 1024
MAX_ENTRIES = 2003
SCHEMAS = Path(__file__).resolve().parents[1] / "references"
MAX_PREVIEW_PIXELS = 16777216
MAX_PREVIEW_DIMENSION = 16384


class Invalid(ValueError):
    """Invalid or unresolved local package."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    value = hashlib.sha256()
    with no_links(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def strict_json(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise Invalid(f"non-JSON number: {value}")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def message_lines(data):
    # splitlines() would corrupt legal JSON strings containing U+2028/U+2029.
    lines = data.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    require(all(line.strip() for line in lines), "blank JSONL lines are not message records")
    require(all(len(line.encode("utf-8")) <= MAX_LINE for line in lines), "JSONL line exceeds 1 MiB")
    return [strict_json(line) for line in lines]


def schema_check(value, schema, root=None, location="$"):
    """Evaluate only the assertion vocabulary used by the pinned canonical schemas.

    This is deliberately not a general JSON Schema implementation. Fail on unfamiliar
    keywords so a future schema update cannot silently weaken validation.
    """
    root = schema if root is None else root
    known = {"$defs", "$ref", "title", "description", "default", "type", "const",
             "enum", "anyOf", "properties", "required", "additionalProperties",
             "items", "minLength", "maxLength", "minItems", "maxItems", "pattern",
             "minimum", "maximum"}
    require(not set(schema) - known, f"unsupported pinned schema assertion at {location}")
    if "$ref" in schema:
        ref = schema["$ref"]
        require(ref.startswith("#/$defs/"), "only local schema references are supported")
        return schema_check(value, root["$defs"][ref.split("/")[-1]], root, location)
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                schema_check(value, branch, root, location)
                break
            except Invalid:
                continue
        else:
            raise Invalid(f"{location}: no matching schema alternative")
    types = {"object": dict, "array": list, "string": str, "integer": int,
             "boolean": bool, "null": type(None)}
    if "type" in schema:
        require(type(value) is types[schema["type"]], f"{location}: expected {schema['type']}")
    if "const" in schema:
        require(value == schema["const"], f"{location}: wrong constant/version")
    if "enum" in schema:
        require(value in schema["enum"], f"{location}: invalid enum")
    if type(value) is dict:
        props = schema.get("properties", {})
        require(not set(schema.get("required", [])) - value.keys(), f"{location}: missing required fields")
        if schema.get("additionalProperties") is False:
            require(not value.keys() - props.keys(), f"{location}: unexpected fields {value.keys() - props.keys()}")
        for key, child in value.items():
            if key in props:
                schema_check(child, props[key], root, f"{location}.{key}")
    if type(value) is list:
        require(len(value) >= schema.get("minItems", 0), f"{location}: too few items")
        require(len(value) <= schema.get("maxItems", MAX_TOTAL), f"{location}: too many items")
        for i, child in enumerate(value):
            if "items" in schema:
                schema_check(child, schema["items"], root, f"{location}[{i}]")
    if type(value) is str:
        require(len(value) >= schema.get("minLength", 0), f"{location}: string too short")
        require(len(value) <= schema.get("maxLength", MAX_TOTAL), f"{location}: string too long")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, f"{location}: invalid pattern")
    if type(value) is int:
        require(value >= schema.get("minimum", value), f"{location}: below minimum")
        require(value <= schema.get("maximum", value), f"{location}: above maximum")


def timestamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None, "timestamp needs explicit UTC offset")
    return parsed


def safe_media(path):
    require(isinstance(path, str) and len(path) <= 240 and path.startswith("media/")
            and re.fullmatch(r"[A-Za-z0-9_./-]+", path) is not None
            and all(part not in ("", ".", "..") for part in path.split("/")),
            f"unsafe media path: {path!r}")
    return path


def media_role(item):
    return item.get("role", "original")


def static_png_size(data):
    """Bounded static PNG validation for the producer's RGB/RGBA 8-bit crops.

    No Pillow/runtime dependency; decode the bounded zlib scanlines, verify CRCs,
    framing and filters. Reject animation, extra data and unsupported producer modes.
    """
    require(data.startswith(b"\x89PNG\r\n\x1a\n"), "screenshot preview must be PNG bytes")
    offset, chunks, compressed = 8, [], []
    width = height = channels = None
    idat_closed = False
    while offset < len(data):
        require(offset + 12 <= len(data), "truncated PNG chunk")
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        require(offset + 12 + size <= len(data), "truncated PNG payload")
        payload = data[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == crc, "PNG CRC mismatch")
        require(kind not in {b"acTL", b"fcTL", b"fdAT"}, "animated PNG is not a static screenshot preview")
        require(not chunks or kind != b"IHDR", "duplicate PNG header")
        if not chunks:
            require(kind == b"IHDR" and size == 13, "PNG needs first IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            require(0 < width <= MAX_PREVIEW_DIMENSION and 0 < height <= MAX_PREVIEW_DIMENSION,
                    "screenshot preview dimensions exceed bounds")
            require(width * height <= MAX_PREVIEW_PIXELS, "screenshot preview pixel budget exceeded")
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                    "producer screenshot previews require non-interlaced 8-bit RGB/RGBA PNG")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            require(not idat_closed, "noncontiguous PNG IDAT")
            compressed.append(payload)
        elif kind == b"IEND":
            require(size == 0 and compressed and offset + 12 == len(data), "PNG trailing data or missing image")
            chunks.append(kind)
            offset += 12
            break
        else:
            if compressed:
                idat_closed = True
            require(kind != b"PLTE", "producer screenshot crops must not carry a palette")
            require(len(kind) == 4 and kind[0] & 32, "unsupported critical PNG chunk")
        chunks.append(kind)
        offset += 12 + size
    require(chunks and chunks[-1] == b"IEND" and offset == len(data), "PNG missing final IEND")
    stride = width * channels + 1
    expected = stride * height
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b"".join(compressed), expected + 1)
    require(len(decoded) == expected and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            "PNG scanline size/stream mismatch")
    require(all(value <= 4 for value in decoded[::stride]), "invalid PNG row filter")
    return width, height


def inventory_semantics(item):
    role = media_role(item)
    if role == "screenshot_preview":
        require(item["completeness"] == "complete" and item["content_type"] == "image/png"
                and item.get("derived_from") is not None and item.get("provenance") is not None,
                "screenshot preview needs complete PNG, original path and provenance")
        safe_media(item["derived_from"])
    else:
        require(item.get("derived_from") is None, "original media cannot be derived")


def safe_entry(name):
    require(name in {"manifest.json", "messages.jsonl"} or safe_media(name),
            f"unexpected package entry: {name}")


def no_links(path):
    # Reject symlinked ancestors too, before resolving; never read through them.
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        system_alias = str(part) in {"/tmp", "/var"} and part.is_symlink() and str(part.resolve()) == "/private" + str(part)
        require(system_alias or not part.is_symlink(), f"symlink is not allowed: {part}")
    return path.resolve()


def read_limited(path):
    path = no_links(path)
    require(path.is_file(), f"missing regular file: {path}")
    require(path.stat().st_size <= MAX_FILE, f"file exceeds {MAX_FILE} byte limit: {path}")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    require(len(data) <= MAX_FILE, "file grew beyond limit")
    return data


def read_entries(path):
    path = no_links(path)
    entries = {}
    folded = set()
    total = 0

    def add(name, data):
        nonlocal total
        safe_entry(name)
        require(name.casefold() not in folded, f"duplicate/casefold path: {name}")
        folded.add(name.casefold())
        total += len(data)
        require(total <= MAX_TOTAL and len(entries) < MAX_ENTRIES, "package exceeds resource limits")
        entries[name] = data

    if path.is_dir():
        def visit(directory):
            for child in sorted(directory.iterdir()):
                no_links(child)
                name = child.relative_to(path).as_posix()
                if child.is_dir():
                    require(name == "media" or name.startswith("media/"), f"unexpected directory: {name}")
                    if name != "media":
                        safe_media(name)
                    visit(child)
                else:
                    add(name, read_limited(child))
        visit(path)
    else:
        require(path.stat().st_size <= MAX_ZIP, "ZIP exceeds 32 MiB upload limit")
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            require(len(infos) <= MAX_ENTRIES, "too many ZIP entries")
            seen = set()
            # Inspect the entire central directory before decompressing any payload.
            for info in infos:
                name = info.filename
                require(info.orig_filename == name, "NUL/aliased ZIP path")
                require(name.casefold() not in seen, f"duplicate/casefold ZIP path: {name}")
                seen.add(name.casefold())
                mode = info.external_attr >> 16
                require(not stat.S_ISLNK(mode) and not info.flag_bits & 1, "symlink/encrypted ZIP entry")
                require(stat.S_IFMT(mode) in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG), "special/mismatched ZIP entry")
                require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "unsupported ZIP compression")
                if info.is_dir():
                    require(name == "media/", f"unexpected ZIP directory: {name}")
                    require(info.file_size == 0, "nonempty directory entry")
                else:
                    safe_entry(name)
                    require(info.file_size <= MAX_FILE, "ZIP entry exceeds file limit")
            require(sum(i.file_size for i in infos) <= MAX_TOTAL, "ZIP exceeds total size limit")
            for info in infos:
                if not info.is_dir():
                    with archive.open(info) as stream:
                        data = stream.read(MAX_FILE + 1)
                    require(len(data) == info.file_size, "invalid ZIP size")
                    add(info.filename, data)
    require({"manifest.json", "messages.jsonl"} <= entries.keys(), "missing root manifest/messages")
    return entries


@dataclass
class Package:
    manifest: dict
    messages: list
    entries: dict

    @property
    def batch_id(self):
        return self.manifest["batch_id"]

    @property
    def by_id(self):
        return {m["id"]: m for m in self.messages}


def parse_entries(entries):
    manifest = strict_json(entries["manifest.json"])
    schema_check(manifest, strict_json((SCHEMAS / f"{VERSION}.manifest.schema.json").read_bytes()))
    message_schema = strict_json((SCHEMAS / f"{VERSION}.message.schema.json").read_bytes())
    messages = message_lines(entries["messages.jsonl"])
    for message in messages:
        schema_check(message, message_schema)
        require((message["id_kind"] == "source") == bool(message["source_id"]), "generated/source identity mismatch")
        require(message["id_kind"] != "generated" or message["source_id"] is None,
                "generated source_id must be null")
        timestamp(message["sent_at"])
    capture = manifest["capture"]
    start, end = timestamp(capture["started_at"]), timestamp(capture["ended_at"])
    timestamp(capture["captured_at"])
    ZoneInfo(capture["timezone"])
    require(not (start and end) or start <= end, "capture range is reversed")
    require(manifest["counts"] == {"messages": len(messages), "attachments": len(manifest["attachments"])}, "counts mismatch")
    require(len({m["id"] for m in messages}) == len(messages), "duplicate message ID")
    orders = [m["order"] for m in messages]
    require(orders == sorted(set(orders)), "message order must be unique and increasing")
    sources = [m["source_id"] for m in messages if m["id_kind"] == "source"]
    require(len(sources) == len(set(sources)), "duplicate source message ID")
    require(manifest["base_batch_id"] != manifest["batch_id"], "batch cannot continue itself")
    require(manifest["base_batch_id"] is not None or not manifest["overlap_anchors"], "baseline cannot have overlap anchors")
    inventory = {}
    folded = set()
    local_paths = set()
    preview_pixels = 0
    for item in manifest["attachments"]:
        path = safe_media(item["path"])
        require(path.casefold() not in folded, "duplicate/casefold inventory path")
        folded.add(path.casefold())
        inventory[path] = item
        inventory_semantics(item)
        if item["completeness"] == "missing":
            require(item["source_batch_id"] is None and path not in entries, "missing media must have no bytes or prior reference")
        else:
            require(item["sha256"] is not None and item["size_bytes"] is not None, "complete media needs hash and size")
            if item["source_batch_id"] is None:
                require(path in entries, f"missing media bytes: {path}")
                data = entries[path]
                require(digest(data) == item["sha256"] and len(data) == item["size_bytes"], f"media hash/size mismatch: {path}")
                if media_role(item) == "screenshot_preview":
                    width, height = static_png_size(data)
                    preview_pixels += width * height
                    require(preview_pixels <= MAX_PREVIEW_PIXELS, "aggregate screenshot preview pixel budget exceeded")
                local_paths.add(path)
            else:
                require(path not in entries, "prior media must not carry local bytes")
    require(set(entries) == {"manifest.json", "messages.jsonl"} | local_paths, "unlisted media or extra package files")
    for item in inventory.values():
        if media_role(item) == "screenshot_preview":
            original = inventory.get(item["derived_from"])
            require(original is not None and media_role(original) == "original" and original["completeness"] == "missing",
                    "screenshot preview must identify a missing original")
    referenced = set()
    for message in messages:
        refs = []
        for ref in message["media"]:
            path = safe_media(ref["path"])
            require(path in inventory, f"media reference not in inventory: {path}")
            item = inventory[path]
            require(all(ref[key] == item[key] for key in ("path", "sha256", "source_batch_id")), "media reference differs from inventory")
            require(media_role(ref) == media_role(item), "media reference role differs from inventory")
            refs.append(path)
            referenced.add(path)
        require(len(refs) == len(set(refs)), "duplicate media reference in one message")
        for path in refs:
            if media_role(inventory[path]) == "screenshot_preview":
                require(inventory[path]["derived_from"] in refs, "preview needs missing original in same message")
        voice = message.get("voice")
        if voice is not None:
            require(message["type"] == "voice", "voice metadata requires type voice")
            require(message["text"] is None, "voice-only message text must stay null; transcript is derived")
            require(any(media_role(inventory[path]) == "original" and inventory[path]["content_type"].startswith("audio/")
                        for path in refs), "voice metadata needs an original audio reference, complete or missing")
    require(referenced == inventory.keys(), "unreferenced attachment inventory")
    coverage = manifest["completeness"]["attachments"]
    missing = any(i["completeness"] == "missing" for i in inventory.values())
    require(coverage != "complete" or not missing, "complete coverage contains missing media")
    require(coverage != "none" or not inventory, "none coverage has attachment inventory")
    require(not missing or bool(manifest["completeness"]["notes"]), "missing media needs completeness notes")
    return Package(manifest, messages, entries)


def original_fingerprint(message):
    # Candidate comparison only. Never identity, never automatic deduplication.
    value = {key: message[key] for key in ("sender", "sent_at", "original_time", "type", "text", "reply_to")}
    value["media"] = [r["sha256"] for r in message["media"] if media_role(r) == "original"]
    voice = message.get("voice")
    if voice:
        duration = {key: voice[key] for key in ("original_duration", "duration_ms") if voice.get(key) is not None}
        if duration:
            value["voice"] = duration
    return digest(encoded(value)[:-1])


def original_evidence_complete(message, inventory):
    return all(inventory[ref["path"]]["completeness"] == "complete"
               for ref in message["media"] if media_role(ref) == "original")


def load_bundle(path, prior_paths=()):
    packages = [parse_entries(read_entries(p)) for p in [*prior_paths, path]]
    by_batch = {}
    for package in packages:
        require(package.batch_id not in by_batch, f"duplicate batch ID: {package.batch_id}")
        by_batch[package.batch_id] = package
    target = packages[-1]
    conversation = target.manifest["conversation_id"]
    require(all(p.manifest["conversation_id"] == conversation for p in packages), "prior package conversation mismatch")
    active, finished = set(), set()

    def visit(package):
        bid = package.batch_id
        require(bid not in active, "cyclic batch chain")
        if bid in finished:
            return
        active.add(bid)
        base_id = package.manifest["base_batch_id"]
        base = None
        ancestors = set()
        if base_id:
            require(base_id in by_batch, f"unresolved base batch: {base_id}")
            base = by_batch[base_id]
            visit(base)
            cursor = base
            while cursor:
                ancestors.add(cursor.batch_id)
                cursor = by_batch.get(cursor.manifest["base_batch_id"])
        for item in package.manifest["attachments"]:
            source = item["source_batch_id"]
            if source:
                require(source in ancestors, f"media source must be a declared ancestor: {source}")
                prior = next((i for i in by_batch[source].manifest["attachments"] if i["path"] == item["path"]), None)
                require(prior is not None and prior["completeness"] == "complete", "unresolved prior media path")
                require(all(prior[k] == item[k] for k in ("sha256", "size_bytes", "content_type")), "prior media identity mismatch")
                require(media_role(prior) == media_role(item) and prior.get("derived_from") == item.get("derived_from"),
                        "prior media role/derivation mismatch")
        for message in package.messages:
            reply = message["reply_to"]
            if reply:
                require(reply["batch_id"] in ancestors | {bid}, "reply target batch not in chain")
                require(reply["message_id"] in by_batch[reply["batch_id"]].by_id, "unresolved reply target")
                require((reply["batch_id"], reply["message_id"]) != (bid, message["id"]), "self reply is not allowed")
        used_current, used_base = set(), set()
        for anchor in package.manifest["overlap_anchors"]:
            require(base is not None, "overlap needs base")
            current, previous = anchor["message_id"], anchor["base_message_id"]
            require(current in package.by_id and previous in base.by_id, "unresolved overlap anchor")
            require(current not in used_current and previous not in used_base, "overlap mapping must be one-to-one")
            used_current.add(current)
            used_base.add(previous)
            require(original_fingerprint(package.by_id[current]) == original_fingerprint(base.by_id[previous]), "overlap originals differ")
            if package.by_id[current]["id_kind"] == "source" and base.by_id[previous]["id_kind"] == "source":
                require(package.by_id[current]["source_id"] == base.by_id[previous]["source_id"], "overlap source IDs differ")
        active.remove(bid)
        finished.add(bid)

    for package in packages:
        visit(package)
    return target, by_batch


def preview(package, by_batch):
    manifest = package.manifest
    base = by_batch.get(manifest["base_batch_id"])
    candidates = []
    candidate_count = 0
    inventory = {item["path"]: item for item in manifest["attachments"]}
    if base:
        index = {}
        for message in base.messages:
            index.setdefault(original_fingerprint(message), []).append(message["id"])
        for current in package.messages:
            matches = index.get(original_fingerprint(current), [])
            if matches:
                candidate_count += 1
                if len(candidates) < 500:
                    base_inventory = {item["path"]: item for item in base.manifest["attachments"]}
                    incomplete = not original_evidence_complete(current, inventory) or any(
                        not original_evidence_complete(base.by_id[mid], base_inventory) for mid in matches[:20])
                    candidates.append({"message_id": current["id"], "base_message_ids": matches[:20],
                                       "base_match_count": len(matches), "truncated": len(matches) > 20,
                                       "status": "ambiguous" if len(matches) > 1 else "incomplete_original" if incomplete else "candidate_only"})
    return {
        "version": VERSION, "conversation_id": manifest["conversation_id"], "title": manifest["title"],
        "batch_id": package.batch_id, "base_batch_id": manifest["base_batch_id"],
        "capture": manifest["capture"], "counts": manifest["counts"],
        "completeness": manifest["completeness"],
        "missing_media": [i for i in manifest["attachments"] if i["completeness"] == "missing"],
        "derived_previews": [i for i in manifest["attachments"] if media_role(i) == "screenshot_preview"],
        "voice_messages": [{"message_id": m["id"], "original_duration": (m.get("voice") or {}).get("original_duration"),
                            "duration_ms": (m.get("voice") or {}).get("duration_ms"),
                            "ui_transcripts": len((m.get("voice") or {}).get("transcripts", [])),
                            "missing_original_audio": [r["path"] for r in m["media"] if media_role(r) == "original"
                                                       and inventory[r["path"]]["completeness"] == "missing"]}
                           for m in package.messages if m.get("voice") is not None],
        "incomplete_original_anchors": [a for a in manifest["overlap_anchors"]
                                        if not original_evidence_complete(package.by_id[a["message_id"]], inventory)],
        "dependencies": sorted({i["source_batch_id"] for i in manifest["attachments"] if i["source_batch_id"]}),
        "unknown_times": [m["id"] for m in package.messages if m["sent_at"] is None],
        "unknown_senders": [m["id"] for m in package.messages if m["sender"]["name"] is None],
        "overlap_candidates": candidates, "overlap_candidate_count": candidate_count,
        "overlap_candidates_truncated": candidate_count > len(candidates),
        "declared_anchors": manifest["overlap_anchors"],
        "notice": "Candidates are not identity decisions. No records were merged. UI scope accuracy needs operator review.",
        "file_sha256": {name: digest(data) for name, data in sorted(package.entries.items())},
    }


def require_review(package, review_path):
    anchors = package.manifest["overlap_anchors"]
    if not anchors:
        return
    require(review_path is not None, "overlap anchors require explicit --review decisions outside ZIP")
    review = strict_json(read_limited(review_path))
    require(type(review) is dict and set(review) == {"batch_id", "decisions"}, "invalid review file")
    require(review["batch_id"] == package.batch_id and type(review["decisions"]) is list, "review batch mismatch")
    decisions = set()
    for entry in review["decisions"]:
        require(type(entry) is dict and set(entry) == {"message_id", "base_message_id", "decision", "evidence"}, "invalid review decision")
        require(entry["decision"] == "same" and type(entry["evidence"]) is str and bool(entry["evidence"].strip()), "review needs same decision and evidence")
        pair = (entry["message_id"], entry["base_message_id"])
        require(pair not in decisions, "duplicate review decision")
        decisions.add(pair)
    require(decisions == {(a["message_id"], a["base_message_id"]) for a in anchors}, "review must match exact anchor mappings")


def checkpoint(package, batches, destination, cursor, authorization):
    """Save an exclusive local progress snapshot outside the package tree."""
    require(cursor.strip() and authorization.strip(), "checkpoint needs UI cursor and scope authorization")
    destination = no_links(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = preview(package, batches)
    state = {"checkpoint_version": 1, "conversation_id": package.manifest["conversation_id"],
             "batch_id": package.batch_id, "base_batch_id": package.manifest["base_batch_id"],
             "capture": package.manifest["capture"], "cursor": cursor, "authorization": authorization,
             "message_hashes": [digest(encoded(m)) for m in package.messages], "preview": report}
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded(state))
    return state


def resume_check(package, batches, state_path):
    state = strict_json(read_limited(state_path))
    require(state.get("checkpoint_version") == 1, "unknown checkpoint version")
    for key in ("conversation_id", "batch_id", "base_batch_id"):
        require(state.get(key) == package.manifest[key], f"resume scope mismatch: {key}")
    for key in ("started_at", "ended_at", "timezone"):
        require(state["capture"][key] == package.manifest["capture"][key], f"resume scope mismatch: {key}")
    previous = state["message_hashes"]
    current = [digest(encoded(m)) for m in package.messages]
    require(type(previous) is list and previous == current[:len(previous)],
            "verified observation prefix changed; do not resume by guessing")
    return {"cursor_to_refind": state["cursor"], "verified_prefix_messages": len(previous),
            "preview": preview(package, batches),
            "notice": "Re-identify this cursor and overlap in the authorized WeCom UI before continuing."}


def create_zip(package, output):
    output = no_links(output)
    require(not output.exists(), f"output exists; refusing to overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".chat-package-", dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            entries = dict(package.entries)
            entries["manifest.json"] = encoded(package.manifest)
            entries["messages.jsonl"] = b"".join(encoded(m) for m in package.messages)
            entries["media/"] = b""
            for name, data in sorted(entries.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o40700 if name.endswith("/") else 0o100600) << 16
                archive.writestr(info, data)
        require(temp.stat().st_size <= MAX_ZIP, "ZIP exceeds 32 MiB upload limit; split into smaller authorized batches")
        # Exclusive destination, atomic completion, no accidental overwrite race.
        os.link(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def normalize(source, output, prior_paths):
    """Canonicalize serialization; fill generated occurrence IDs, local hashes/counts.

    Input is a canonical-layout working directory. No text/time/sender inference, no
    sorting, deduplication, media transcoding or silently repairing unsafe paths.
    """
    entries = read_entries(source)
    manifest = strict_json(entries["manifest.json"])
    messages = message_lines(entries["messages.jsonl"])
    require(type(manifest) is dict and type(manifest.get("batch_id")) is str, "normalization needs batch_id")
    for message in messages:
        if message.get("id") is None:
            require(message.get("source_id") is None and message.get("id_kind") == "generated", "cannot generate a source ID")
            require(type(message.get("order")) is int and message["order"] >= 0, "generated ID needs observation order")
            message["id"] = f"g-{digest(manifest['batch_id'].encode())[:24]}-{message['order']}"
    for item in manifest["attachments"]:
        path = safe_media(item["path"])
        if item["completeness"] == "complete" and item["source_batch_id"] is None:
            require(path in entries, f"missing media bytes: {path}")
            item["sha256"], item["size_bytes"] = digest(entries[path]), len(entries[path])
            for message in messages:
                for ref in message["media"]:
                    if ref["path"] == path and ref["source_batch_id"] is None:
                        ref["sha256"] = item["sha256"]
    manifest["counts"] = {"messages": len(messages), "attachments": len(manifest["attachments"])}
    entries["manifest.json"] = encoded(manifest)
    entries["messages.jsonl"] = b"".join(encoded(m) for m in messages)
    parse_entries(entries)
    output = no_links(output)
    require(not output.exists(), "normalized output directory already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".chat-normalize-", dir=output.parent))
    try:
        for name, data in entries.items():
            dest = temp / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (temp / "media").mkdir(exist_ok=True)
        package, batches = load_bundle(temp, prior_paths)
        os.rename(temp, output)
        return preview(package, batches)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def stage_media(source, directory, original_name=None, content_type="application/octet-stream",
                role="original", derived_from=None, provenance=None):
    """Copy an explicitly downloaded file unchanged, returning safe inventory metadata."""
    data = read_limited(source)
    directory = no_links(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sha = digest(data)
    metadata = {"path": "media/staged.bin", "original_name": original_name if original_name is not None else Path(source).name,
                "sha256": sha, "size_bytes": len(data), "content_type": content_type,
                "completeness": "complete", "source_batch_id": None,
                "role": role, "derived_from": derived_from, "provenance": provenance}
    manifest_schema = strict_json((SCHEMAS / f"{VERSION}.manifest.schema.json").read_bytes())
    schema_check(metadata, manifest_schema["$defs"]["InventoryItem"], manifest_schema)
    inventory_semantics(metadata)
    if role == "screenshot_preview":
        static_png_size(data)
    # Opaque names avoid display-filename traversal and preserve same-byte occurrences.
    index = 1
    while True:
        name = f"{sha}-{index:04d}.bin"
        target = directory / name
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            index += 1
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    metadata["path"] = f"media/{name}"
    return metadata


def prepare_voice_record(spec, media_directory):
    """Prepare one caller-observed UI voice occurrence; no audio/transcription APIs."""
    require(type(spec) is dict and set(spec) == {"message", "audio"}, "voice spec needs only message and audio")
    message, audio = copy.deepcopy(spec["message"]), spec["audio"]
    require(type(audio) is dict and set(audio) == {"file", "original_name", "content_type", "missing_reason"},
            "audio spec needs file, original_name, content_type and missing_reason")
    require(message.get("type") == "voice" and message.get("text") is None and message.get("media") == [],
            "voice record requires type voice, null original text, and empty incoming refs")
    require(type(audio["content_type"]) is str and audio["content_type"].startswith("audio/"), "voice original needs audio MIME kind")
    message.setdefault("voice", {"original_duration": None, "duration_ms": None, "transcripts": []})
    message_schema = strict_json((SCHEMAS / f"{VERSION}.message.schema.json").read_bytes())
    schema_check(message, message_schema)
    require(message["voice"] is not None, "voice record requires explicit voice metadata (unknown values may be null)")
    require((message["id_kind"] == "source") == bool(message["source_id"]), "voice source identity mismatch")
    require(message["id_kind"] != "generated" or message["source_id"] is None, "generated source ID must be null")
    timestamp(message["sent_at"])
    item = None
    staged = None
    try:
        if audio["file"] is None:
            require(type(audio["missing_reason"]) is str and bool(audio["missing_reason"].strip()), "missing audio needs an explicit gap reason")
            message["provenance"]["notes"] = ((message["provenance"].get("notes") or "") + " Original audio missing: " + audio["missing_reason"]).strip()
            item = {"path": f"media/missing-voice-{digest(message['id'].encode())[:24]}.bin", "original_name": audio["original_name"],
                    "sha256": None, "size_bytes": None, "content_type": audio["content_type"], "completeness": "missing",
                    "source_batch_id": None, "role": "original", "derived_from": None, "provenance": message["provenance"]}
        else:
            require(type(audio["file"]) is str and audio["missing_reason"] is None, "complete voice audio needs local file and no missing reason")
            item = stage_media(Path(audio["file"]), media_directory, audio["original_name"], audio["content_type"], provenance=message["provenance"])
            staged = no_links(media_directory) / Path(item["path"]).name
        message["media"] = [{key: item[key] for key in ("path", "sha256", "source_batch_id", "role")}]
        schema_check(message, message_schema)
        manifest_schema = strict_json((SCHEMAS / f"{VERSION}.manifest.schema.json").read_bytes())
        schema_check(item, manifest_schema["$defs"]["InventoryItem"], manifest_schema)
        return {"message": message, "attachment": item}
    except Exception:
        if staged is not None:
            staged.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "preview", "pack", "normalize", "checkpoint", "resume-check"):
        sub = subs.add_parser(command)
        sub.add_argument("source", type=Path)
        sub.add_argument("--prior", type=Path, action="append", default=[], help="explicit authorized prior ZIP/directory; repeat for chain")
        if command in ("pack", "normalize"):
            sub.add_argument("--output", type=Path, required=True)
        if command == "pack":
            sub.add_argument("--review", type=Path)
        if command in ("checkpoint", "resume-check"):
            sub.add_argument("--checkpoint", type=Path, required=True)
        if command == "checkpoint":
            sub.add_argument("--cursor", required=True)
            sub.add_argument("--authorization", required=True)
    sub = subs.add_parser("stage-media")
    sub.add_argument("source", type=Path)
    sub.add_argument("--media-dir", type=Path, required=True)
    sub.add_argument("--original-name")
    sub.add_argument("--content-type", default="application/octet-stream")
    sub.add_argument("--role", choices=("original", "screenshot_preview"), default="original")
    sub.add_argument("--derived-from")
    sub.add_argument("--provenance-file", type=Path)
    sub = subs.add_parser("voice-record")
    sub.add_argument("source", type=Path, help="UI observation JSON, not audio for transcription")
    sub.add_argument("--media-dir", type=Path, required=True)
    sub.add_argument("--output", type=Path, required=True, help="new private record JSON; transcript not printed")
    args = parser.parse_args()
    try:
        if args.command == "stage-media":
            provenance = strict_json(read_limited(args.provenance_file)) if args.provenance_file else None
            result = stage_media(args.source, args.media_dir, args.original_name, args.content_type,
                                 args.role, args.derived_from, provenance)
        elif args.command == "voice-record":
            output = no_links(args.output)
            require(not output.exists(), "voice record output already exists")
            spec = strict_json(read_limited(args.source))
            audio_path = spec.get("audio", {}).get("file")
            if isinstance(audio_path, str) and not Path(audio_path).is_absolute():
                spec["audio"]["file"] = str(no_links(args.source).parent / audio_path)
            record = prepare_voice_record(spec, args.media_dir)
            output.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded(record))
            result = {"output": str(output), "message_id": record["message"]["id"],
                      "audio_completeness": record["attachment"]["completeness"],
                      "ui_transcripts": len(record["message"]["voice"].get("transcripts", []))}
        elif args.command == "normalize":
            result = normalize(args.source, args.output, args.prior)
        else:
            package, batches = load_bundle(args.source, args.prior)
            result = preview(package, batches)
            if args.command == "pack":
                require_review(package, args.review)
                create_zip(package, args.output)
                result["output"] = str(args.output)
                result["zip_sha256"] = file_digest(args.output)
            elif args.command == "checkpoint":
                source = no_links(args.source)
                destination = no_links(args.checkpoint)
                require(not source.is_dir() or source not in destination.parents,
                        "checkpoint must stay outside package directory")
                result = checkpoint(package, batches, destination, args.cursor, args.authorization)
            elif args.command == "resume-check":
                result = resume_check(package, batches, args.checkpoint)
        print(encoded(result).decode(), end="")
        return 0
    except (Invalid, OSError, ValueError, KeyError, TypeError, RecursionError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
