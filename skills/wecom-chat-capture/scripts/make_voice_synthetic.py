#!/usr/bin/env python3
"""Invent voice/original/WeCom-transcript/missing/sticker-preview v1 test records."""
from __future__ import annotations

import copy
import io
from pathlib import Path
import struct
import wave
import zlib
import argparse

import chat_package as cp


def invented_png(width=16, height=16):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    rows = (b"\0" + b"\x20\x80\xc0" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def generate(output):
    output = cp.no_links(output)
    cp.require(not output.exists(), "synthetic voice output already exists")
    baseline = output / "baseline"
    media = baseline / "media"
    media.mkdir(parents=True)
    provenance = {"source": "synthetic", "capture_method": "invented visible-UI fixture, no real capture",
                  "locator": "synthetic:voice-viewport", "notes": "Invented test data only."}
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000)
    (output / "synthetic-original.wav").write_bytes(stream.getvalue())

    def message(index, duration, milliseconds=None, transcripts=None):
        return {"id": f"voice-generated-{index}", "id_kind": "generated", "source_id": None,
                "sender": {"id": None, "name": "合成语音成员", "is_self": False},
                "sent_at": None, "original_time": "10/19 9:30", "order": index, "type": "voice",
                "text": None, "reply_to": None, "media": [], "provenance": copy.deepcopy(provenance),
                "voice": {"original_duration": duration, "duration_ms": milliseconds, "transcripts": transcripts or []}}

    transcript = {"text": "这是合成的界面转写示例。", "source": "wecom_ui",
                  "provenance": {"source": "synthetic_wecom_ui", "capture_method": "invented WeCom-derived transcript display",
                                 "locator": "synthetic:transcript-2", "notes": "Derived UI transcription, not original sender text."}}
    specs = [
        {"message": message(0, '1″', 1000), "audio": {"file": "synthetic-original.wav", "original_name": "合成语音.wav", "content_type": "audio/wav", "missing_reason": None}},
        {"message": message(1, '12″', 12000, [transcript]), "audio": {"file": None, "original_name": None, "content_type": "audio/unknown", "missing_reason": "Synthetic original export unavailable; only UI-derived transcription visible."}},
        {"message": message(2, '7″'), "audio": {"file": None, "original_name": None, "content_type": "audio/unknown", "missing_reason": "Synthetic original export and UI transcription both unavailable; occurrence retained."}},
    ]
    names = ("voice-original.spec.json", "voice-transcript-only.spec.json", "voice-missing-both.spec.json")
    messages, inventory = [], []
    for spec, name in zip(specs, names):
        (output / name).write_bytes(cp.encoded(spec))
        local = copy.deepcopy(spec)
        if local["audio"]["file"]:
            local["audio"]["file"] = str(output / local["audio"]["file"])
        record = cp.prepare_voice_record(local, media)
        messages.append(record["message"])
        inventory.append(record["attachment"])

    missing = {"path": "media/missing-synthetic-sticker.gif", "original_name": None, "sha256": None,
               "size_bytes": None, "content_type": "image/gif", "completeness": "missing", "source_batch_id": None,
               "role": "original", "derived_from": None, "provenance": provenance}
    (output / "synthetic-preview.png").write_bytes(invented_png())
    preview = cp.stage_media(output / "synthetic-preview.png", media, "synthetic-screenshot-derived.png", "image/png",
                             role="screenshot_preview", derived_from=missing["path"],
                             provenance={"source": "synthetic", "capture_method": "invented screenshot crop, no actual screenshot",
                                         "locator": "synthetic:sticker-frame", "notes": "Derived static preview only. Original animation missing."})
    sticker = message(3, None)
    sticker.update(type="sticker", voice=None,
                   media=[{key: item[key] for key in ("path", "sha256", "source_batch_id", "role")} for item in (missing, preview)])
    messages.append(sticker)
    inventory.extend([missing, preview])
    manifest = {"version": cp.VERSION, "conversation_id": "synthetic-voice-sticker-room", "title": "Synthetic voice and sticker examples",
                "batch_id": "synthetic-voice-sticker-baseline", "base_batch_id": None,
                "capture": {"started_at": None, "ended_at": None, "captured_at": "2026-10-19T10:00:00+08:00", "timezone": "Asia/Shanghai"},
                "counts": {"messages": len(messages), "attachments": len(inventory)}, "attachments": inventory,
                "completeness": {"history": "partial", "attachments": "partial", "notes": [
                    "Invented voice/sticker fixtures only; no real group searched or captured.",
                    "Two voice audio originals and one animated sticker original are missing. UI transcript/static preview do not recover originals."]},
                "provenance": provenance, "overlap_anchors": []}
    (baseline / "manifest.json").write_bytes(cp.encoded(manifest))
    (baseline / "messages.jsonl").write_bytes(b"".join(cp.encoded(m) for m in messages))
    cp.load_bundle(baseline)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(generate(parser.parse_args().output))
