"""Validate Slinx import bytes and save a JSONL/media archive without an HTML view."""
from datetime import datetime
from uuid import uuid4
from pathlib import Path
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile


def import_messages(path):
    """Keep native replies; preserve an unresolved visible quote exactly once."""
    from app.dev_chat_archive import strict_json
    encoded = io.BytesIO()
    with path.open("rb") as records:
        for line in records:
            row = strict_json(line)
            if "quoted_excerpt" not in row:
                encoded.write(line)
                continue
            excerpt = row.pop("quoted_excerpt")
            if excerpt is not None:
                if (not isinstance(excerpt, dict) or set(excerpt) != {"sender_name", "original_time", "text"}
                        or not isinstance(excerpt["text"], str) or not excerpt["text"]
                        or any(excerpt[k] is not None and not isinstance(excerpt[k], str)
                               for k in ("sender_name", "original_time"))):
                    raise ValueError("Invalid staging quote for " + row["id"])
                body = row["text"]
                if body is not None and not isinstance(body, str):
                    raise ValueError("Invalid reply text for " + row["id"])
                if row["reply_to"] is None:
                    # An ambiguous reference has no native target. Keep its visible evidence in the ZIP.
                    author = excerpt["sender_name"] or "Unknown sender"
                    if excerpt["original_time"]:
                        author += " · " + excerpt["original_time"]
                    row["text"] = author + " — " + excerpt["text"]
                    if body:
                        row["text"] += "\n\n" + body
            encoded.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf8"))
    return encoded.getvalue()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def local_file(stage, name):
    if (not isinstance(name, str) or not re.fullmatch(r"(?:media|originals|captures)/[A-Za-z0-9_./-]+", name)
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("Use a safe relative media/, originals/ or captures/ path.")
    path = (stage / name).resolve()
    if not path.is_relative_to(stage.resolve()) or not path.is_file():
        raise ValueError("Referenced file is missing or outside staging: " + name)
    return path


def source_records(stage, package):
    """Check source identities, parent/reply links and imported attachment ownership."""
    from app.dev_chat_archive import strict_json
    path = stage / "source-messages.jsonl"
    if not path.is_file():
        raise ValueError("Prepare source-messages.jsonl with the chat header and verified source records first.")
    raw = path.read_bytes()
    rows = [strict_json(line) for line in raw.split(b"\n") if line.strip()]
    if len(rows) < 2 or not isinstance(rows[0], dict):
        raise ValueError("Source JSONL needs one chat header followed by messages.")
    header, messages = rows[0], rows[1:]
    if (header.get("record_type") != "chat" or header.get("schema_version") != "wecom-evidence-v2"
            or any(not isinstance(header.get(key), str) or not header[key]
                   for key in ("source_namespace", "chat_id", "chat_name", "export_id"))):
        raise ValueError("Invalid source chat header.")
    imported = {msg.id: msg for msg in package.messages}
    inventory = {item.path: item for item in package.manifest.attachments}
    by_id, last_order, roots, files, mapped_media = {}, {}, set(), {}, set()
    required = {"message_id", "id_kind", "source_message_id", "chat_id", "parent_message_id", "order",
                "sender_id", "sender_name", "from_me", "sent_at", "original_time", "time_precision",
                "timezone", "message_type", "text", "reply_to", "media", "forward_status", "provenance", "slinx_ref"}
    for row in messages:
        if not isinstance(row, dict) or row.get("record_type") != "message" or not required <= row.keys():
            raise ValueError("Source message is missing required fields.")
        ident = row["message_id"]
        if not isinstance(ident, str) or not ident or ident in by_id or row["chat_id"] != header["chat_id"]:
            raise ValueError("Source IDs must be unique within the stated chat.")
        by_id[ident] = row
        parent, order = row["parent_message_id"], row["order"]
        if parent is not None and not isinstance(parent, str):
            raise ValueError("Invalid parent ID.")
        if type(order) is not int or order < 0 or order <= last_order.get(parent, -1):
            raise ValueError("Source sibling order must be strictly increasing.")
        last_order[parent] = order
        if row["time_precision"] not in {"second", "minute", "date", "unknown"}:
            raise ValueError("Invalid time precision.")
        if row["sent_at"] is not None:
            stamp = row["sent_at"]
            if (not isinstance(stamp, str) or not re.search(r"T\d{2}:\d{2}:\d{2}", stamp)
                    or row["time_precision"] != "second" or not row["timezone"]
                    or datetime.fromisoformat(stamp.replace("Z", "+00:00")).utcoffset() is None):
                raise ValueError("sent_at requires observed seconds, timezone and an explicit offset.")
        link = row["slinx_ref"]
        if (not isinstance(link, dict) or set(link) != {"batch_id", "message_id"}
                or link["batch_id"] != package.manifest.batch_id or link["message_id"] not in imported):
            raise ValueError("Source record does not map to this Slinx batch.")
        if parent is None:
            if link["message_id"] in roots:
                raise ValueError("Two top-level records cannot map to one imported message.")
            roots.add(link["message_id"])
        if not isinstance(row["media"], list):
            raise ValueError("Source media must be an array.")
        for attachment in row["media"]:
            if not isinstance(attachment, dict):
                raise ValueError("Invalid source attachment.")
            if attachment.get("attachment_status") == "exported" and not attachment.get("attachment_path"):
                raise ValueError("An exported original needs its actual local file.")
            variants = []
            if attachment.get("attachment_path"):
                variants.append({**attachment, "path": attachment["attachment_path"]})
            variants.extend(v for v in (attachment.get("import_copy"), attachment.get("preview")) if v)
            for variant in variants:
                source = local_file(stage, variant["path"])
                size, digest = source.stat().st_size, file_hash(source)
                if size != variant.get("size_bytes") or digest != variant.get("sha256"):
                    raise ValueError("Source media bytes do not match their size/hash.")
                files[variant["path"]] = (source, digest, size)
            slinx_path = attachment.get("slinx_path")
            if slinx_path is not None:
                item = inventory.get(slinx_path)
                if item is None or slinx_path not in {ref.path for ref in imported[link["message_id"]].media}:
                    raise ValueError("Attachment maps to the wrong Slinx message.")
                if item.completeness == "complete" and not any(
                    v.get("path") == slinx_path and v.get("sha256") == item.sha256 for v in variants
                ):
                    raise ValueError("A complete imported attachment needs its matching local variant.")
                mapped_media.add(slinx_path)
        if not isinstance(row["provenance"], dict):
            raise ValueError("Source provenance must be an object.")
        for name in row["provenance"].get("evidence_paths", []):
            source = local_file(stage, name)
            files[name] = (source, file_hash(source), source.stat().st_size)
    if roots != set(imported) or mapped_media != set(inventory):
        raise ValueError("Every imported message and attachment needs source mapping.")
    for row in messages:
        seen, ancestor = {row["message_id"]}, row
        while ancestor["parent_message_id"] is not None:
            parent = ancestor["parent_message_id"]
            if parent in seen or parent not in by_id:
                raise ValueError("Missing or circular source parent.")
            seen.add(parent)
            ancestor = by_id[parent]
            if ancestor["message_type"] != "forward":
                raise ValueError("An internal message must belong to a forwarded card.")
        if row["slinx_ref"] != ancestor["slinx_ref"]:
            raise ValueError("Internal message maps to a different outer Slinx message.")
        reply = row["reply_to"]
        if reply is not None and (not isinstance(reply, dict) or (
                reply.get("status") == "matched" and (reply.get("message_id") not in by_id
                                                       or reply["message_id"] == row["message_id"]))):
            raise ValueError("Unresolved matched source reply.")
    return raw, header, messages, files


def main(repo, stage, dest=None):
    sys.path.insert(0, str(repo.resolve() / "backend"))
    from app.dev_chat_archive import parse
    from app.dev_chat_contract import safe_path
    os.umask(0o077)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(stage / "manifest.json", "manifest.json")
        records = import_messages(stage / "messages.jsonl")
        record_info = zipfile.ZipInfo.from_file(stage / "messages.jsonl", "messages.jsonl")
        archive.writestr(record_info, records, compress_type=zipfile.ZIP_DEFLATED)
        manifest = json.loads((stage / "manifest.json").read_text(encoding="utf8"))
        for item in manifest["attachments"]:
            if item["completeness"] == "complete" and item["source_batch_id"] is None:
                name = safe_path(item["path"])
                archive.write(local_file(stage, name), name)
    package = parse(data.getvalue(), production=True)
    original, header, messages, files = source_records(stage, package)
    report_file = stage / "export-report.json"
    report = json.loads(report_file.read_text(encoding="utf8")) if report_file.is_file() else {}
    if not isinstance(report, dict):
        raise ValueError("Export report must be an object.")
    report["packaging"] = {
        "source_schema": header["schema_version"], "export_id": header["export_id"],
        "slinx_conversation_id": package.manifest.conversation_id, "batch_id": package.manifest.batch_id,
        "top_level_messages": len(package.messages), "source_messages": len(messages),
        "inner_messages": sum(row["parent_message_id"] is not None for row in messages),
        "source_jsonl_sha256": hashlib.sha256(original).hexdigest(),
        "zip_bytes": len(package.raw), "zip_sha256": package.sha256,
        "source_mapping": "passed", "local_slinx_parser": "passed", "live_import": "not_performed",
        "capture_completeness": "See capture report and per-message provenance; not verified by packager.",
        "files": {name: {"sha256": digest, "size_bytes": size}
                  for name, (_path, digest, size) in files.items()},
    }
    if dest is None:
        tag = package.manifest.conversation_id[:80].replace(":", "-")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = Path.home() / "Downloads" / "data" / f"{tag}-{stamp}-{uuid4().hex[:8]}"
    if dest.exists() or stage.resolve() in dest.resolve().parents:
        raise SystemExit("Choose a new output directory outside staging.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
        ready = Path(temp) / "result"
        ready.mkdir()
        (ready / "media").mkdir()
        (ready / "slinx-import.zip").write_bytes(data.getvalue())
        (ready / "messages.jsonl").write_bytes(original)
        for name, (source, digest, _size) in files.items():
            path = ready / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
            if file_hash(path) != digest:
                raise ValueError("Attachment changed while copying.")
        (ready / "export-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        ready.rename(dest)
    print(dest.resolve())
    print(f"Validated {len(package.messages)} imported messages, {len(messages)} source messages and {len(package.media)} imported attachments.")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: finish.py REPO STAGING [NEW_OUTPUT]")
    main(*(Path(arg) for arg in sys.argv[1:]))
