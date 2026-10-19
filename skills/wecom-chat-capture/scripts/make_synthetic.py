#!/usr/bin/env python3
"""Generate ONLY invented mixed-media baseline/delta examples in a new directory."""
from __future__ import annotations

import argparse
import copy
import io
import json
from pathlib import Path
import struct
import wave
import zlib

import chat_package as cp


def json_file(path, value):
    path.write_bytes(cp.encoded(value))


def generate(output):
    output = cp.no_links(output)
    cp.require(not output.exists(), "example output already exists")
    baseline, delta = output / "baseline", output / "delta"
    for root in (baseline, delta):
        (root / "media").mkdir(parents=True)
    provenance = {"source": "synthetic", "capture_method": "invented fixture, no UI capture",
                  "locator": "fixture:viewport-1", "notes": "No real chat data."}

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"\0\x20\x80\xc0")) + chunk(b"IEND", b"")
    audio = io.BytesIO()
    with wave.open(audio, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\0\0" * 80)
    media = [("image.png", "示例图片.png", "image/png", png),
             ("notes.txt", "../原始显示名.txt", "text/plain", "Invented attachment.\n合成数据。\n".encode()),
             ("voice.wav", "语音.wav", "audio/wav", audio.getvalue())]
    inventory = []
    for name, original, kind, data in media:
        (baseline / "media" / name).write_bytes(data)
        inventory.append({"path": f"media/{name}", "original_name": original, "sha256": cp.digest(data),
                          "size_bytes": len(data), "content_type": kind, "completeness": "complete", "source_batch_id": None})
    inventory.append({"path": "media/unavailable-video.bin", "original_name": "过期视频.mp4", "sha256": None,
                      "size_bytes": None, "content_type": "video/mp4", "completeness": "missing", "source_batch_id": None})

    def ref(item):
        return {key: item[key] for key in ("path", "sha256", "source_batch_id")}

    def msg(number, text, kind="text", attachment=None):
        return {"id": f"base-g{number}", "id_kind": "generated", "source_id": None,
                "sender": {"id": None, "name": "合成成员 A", "is_self": False},
                "sent_at": "2026-10-19T10:00:00+08:00", "original_time": "10:00", "order": number,
                "type": kind, "text": text, "reply_to": None,
                "media": [] if attachment is None else [ref(attachment)], "provenance": copy.deepcopy(provenance)}

    messages = [msg(0, "收到 ✅\n原文保留"), msg(1, "收到 ✅\n原文保留"),
                msg(2, None, "image", inventory[0]), msg(3, "附件", "file", inventory[1]),
                msg(4, None, "audio", inventory[2]), msg(5, "回复：收到 ✅\n原文保留", "reply"),
                msg(6, "[视频已过期]", "video", inventory[3]), msg(7, "时间未完整显示")]
    messages[5]["reply_to"] = {"batch_id": "synthetic-baseline-001", "message_id": "base-g1"}
    messages[7]["sent_at"] = None
    messages[7]["original_time"] = "昨天"
    messages[7]["provenance"]["notes"] = "Relative date cannot be established; no guessed timestamp."
    manifest = {"version": cp.VERSION, "conversation_id": "synthetic-conversation-001", "title": "Synthetic only 合成会话",
                "batch_id": "synthetic-baseline-001", "base_batch_id": None,
                "capture": {"started_at": "2026-10-18T00:00:00+08:00", "ended_at": "2026-10-19T10:05:00+08:00",
                            "captured_at": "2026-10-19T10:06:00+08:00", "timezone": "Asia/Shanghai"},
                "counts": {"messages": len(messages), "attachments": len(inventory)}, "attachments": inventory,
                "completeness": {"history": "partial", "attachments": "partial",
                                 "notes": ["Synthetic bounded UI example, not a full server archive.",
                                           "Video original unavailable; no thumbnail substituted.", "One absolute message timestamp unknown."]},
                "provenance": provenance, "overlap_anchors": []}
    json_file(baseline / "manifest.json", manifest)
    (baseline / "messages.jsonl").write_bytes(b"".join(cp.encoded(m) for m in messages))

    delta_inventory = copy.deepcopy(inventory[:1])
    delta_inventory[0]["source_batch_id"] = manifest["batch_id"]
    delta_messages = [copy.deepcopy(messages[1]), copy.deepcopy(messages[2]), msg(2, "新增消息；不合并相同原文")]
    for i, message in enumerate(delta_messages):
        message["id"] = f"delta-g{i}"
        message["order"] = i
        message["provenance"]["locator"] = "fixture:viewport-2"
    delta_messages[1]["media"] = [ref(delta_inventory[0])]
    delta_messages[2]["sent_at"] = "2026-10-19T10:04:00+08:00"
    delta_messages[2]["original_time"] = "10:04"
    delta_messages[2]["reply_to"] = {"batch_id": manifest["batch_id"], "message_id": "base-g1"}
    delta_manifest = copy.deepcopy(manifest)
    delta_manifest.update({"batch_id": "synthetic-delta-001", "base_batch_id": manifest["batch_id"],
                           "attachments": delta_inventory, "counts": {"messages": 3, "attachments": 1},
                           "overlap_anchors": [{"message_id": "delta-g0", "base_message_id": "base-g1"},
                                               {"message_id": "delta-g1", "base_message_id": "base-g2"}],
                           "completeness": {"history": "partial", "attachments": "complete",
                                            "notes": ["Synthetic incremental range; original repeated occurrence reviewed."]}})
    json_file(delta / "manifest.json", delta_manifest)
    (delta / "messages.jsonl").write_bytes(b"".join(cp.encoded(m) for m in delta_messages))
    json_file(output / "delta-review.json", {"batch_id": delta_manifest["batch_id"], "decisions": [
        {**anchor, "decision": "same", "evidence": "Synthetic ordered viewport anchor explicitly identifies this occurrence."}
        for anchor in delta_manifest["overlap_anchors"]]})
    json_file(output / "checkpoint.example.json", {
        "synthetic": True, "batch_id": delta_manifest["batch_id"], "conversation_id": manifest["conversation_id"],
        "scope": manifest["capture"], "authorization": "Synthetic fixture generation only; no UI capture.",
        "last_verified_viewport": "fixture:viewport-2", "last_verified_ids": ["delta-g0", "delta-g1"],
        "resume_state": "reviewed", "pending_media": ["media/unavailable-video.bin"],
        "pending_overlap_candidates": [], "derived": []})
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(generate(args.output))
