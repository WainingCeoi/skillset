#!/usr/bin/env python3
"""Losslessly crop an authorized local screenshot PNG; no UI or network access."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import struct
import sys
import tempfile
import zlib

import chat_package as cp


def png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


def paeth(left, above, upper_left):
    prediction = left + above - upper_left
    distances = (abs(prediction - left), abs(prediction - above), abs(prediction - upper_left))
    return (left, above, upper_left)[distances.index(min(distances))]


def crop_png(data, box):
    """Return a pixel-exact crop of the validated RGB/RGBA screenshot subset."""
    width, height = cp.static_png_size(data)
    cp.require(len(box) == 4 and all(type(value) is int for value in box), "box needs four integer pixel values")
    x, y, crop_width, crop_height = box
    cp.require(x >= 0 and y >= 0 and crop_width > 0 and crop_height > 0
               and x + crop_width <= width and y + crop_height <= height,
               "crop box must be positive and within source screenshot pixels")
    compressed, appearance = [], []
    offset = 8
    header = None
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + size]
        if kind == b"IHDR":
            header = payload
        elif kind == b"IDAT":
            compressed.append(payload)
        elif kind in {b"sRGB", b"gAMA", b"iCCP", b"cHRM", b"tRNS"}:
            appearance.append((kind, payload))
        offset += 12 + size
    channels = 3 if header[9] == 2 else 4
    for kind, payload in appearance:
        cp.require(kind != b"tRNS" or channels == 3 and len(payload) == 6, "invalid RGB transparency chunk")
    stride = width * channels
    # static_png_size already checked bounded stream length; retain the same bound here.
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b"".join(compressed), (stride + 1) * height + 1)
    previous = bytearray(stride)
    cropped = []
    for row_index in range(height):
        start = row_index * (stride + 1)
        mode = decoded[start]
        row = bytearray(decoded[start + 1:start + 1 + stride])
        for index in range(stride) if mode else ():
            left = row[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = above
            elif mode == 3:
                predictor = (left + above) // 2
            else:
                predictor = paeth(left, above, upper_left)
            row[index] = (row[index] + predictor) & 255
        if y <= row_index < y + crop_height:
            cropped.append(b"\0" + bytes(row[x * channels:(x + crop_width) * channels]))
        previous = row
    output_header = struct.pack(">II", crop_width, crop_height) + header[8:]
    result = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", output_header)
              + b"".join(png_chunk(kind, payload) for kind, payload in appearance)
              + png_chunk(b"IDAT", zlib.compress(b"".join(cropped), 9)) + png_chunk(b"IEND", b""))
    cp.static_png_size(result)
    return result


def crop_file(source, box, output):
    source, output = cp.no_links(source), cp.no_links(output)
    cp.require(source != output and not output.exists(), "crop output must be new; refusing to overwrite")
    data = crop_png(cp.read_limited(source), box)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".wecom-crop-", dir=output.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        # mkstemp creates 0600; link publishes complete bytes and refuses overwrite races.
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"output": str(output), "box": list(box), "width": box[2], "height": box[3],
            "sha256": cp.digest(data), "notice": "Exact static screenshot pixels; no original media recovered."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--box", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"), required=True,
                        help="crop rectangle in source screenshot pixels")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(cp.encoded(crop_file(args.source, args.box, args.output)).decode(), end="")
        return 0
    except (cp.Invalid, OSError, ValueError, TypeError, struct.error, zlib.error) as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
