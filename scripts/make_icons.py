#!/usr/bin/env python3
"""Generate the site's PNG icons (beer mug on a dark red rounded square).

Usage: python3 scripts/make_icons.py   (writes into site/)
Standard library only (zlib + struct). Re-run only if you change the design.
"""

import os
import struct
import zlib

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512, "favicon.png": 64}

BG = (122, 18, 28)        # deep cranberry
BEER = (245, 177, 38)     # amber
FOAM = (255, 250, 238)
GLASS = (255, 236, 200)
STAR = (255, 214, 102)


def in_rect(x, y, x0, y0, x1, y1):
    return x0 <= x <= x1 and y0 <= y <= y1


def in_circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def color_at(x, y, maskable):
    """x, y in 0..1. Full-bleed background (safe for maskable icons)."""
    # Mug body occupies the central ~60% so it survives maskable cropping.
    body = (0.30, 0.36, 0.64, 0.80)
    if in_rect(x, y, *body):
        # Glass edge and vertical highlights.
        if x < body[0] + 0.03 or x > body[2] - 0.03 or y > body[3] - 0.03:
            return GLASS
        if in_rect(x, y, 0.38, 0.42, 0.41, 0.74):
            return (255, 214, 120)
        return BEER
    # Handle: ring on the right.
    cx, cy = 0.66, 0.58
    if in_circle(x, y, cx, cy, 0.13) and not in_circle(x, y, cx, cy, 0.075) and x > 0.64:
        return GLASS
    # Foam: bumpy row of circles on top.
    for fx, fr in ((0.34, 0.07), (0.44, 0.08), (0.54, 0.08), (0.62, 0.065)):
        if in_circle(x, y, fx, 0.35, fr):
            return FOAM
    # A small star top-right for festivity.
    if in_circle(x, y, 0.78, 0.22, 0.035) or (abs(x - 0.78) < 0.012 and abs(y - 0.22) < 0.08) \
            or (abs(y - 0.22) < 0.012 and abs(x - 0.78) < 0.08):
        return STAR
    return BG


def render(size, samples=4):
    rows = []
    for py in range(size):
        row = bytearray([0])  # filter type 0
        for px in range(size):
            acc = [0, 0, 0]
            for sy in range(samples):
                for sx in range(samples):
                    c = color_at((px + (sx + 0.5) / samples) / size,
                                 (py + (sy + 0.5) / samples) / size, True)
                    acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]
            n = samples * samples
            row += bytes((acc[0] // n, acc[1] // n, acc[2] // n))
        rows.append(bytes(row))
    return b"".join(rows)


def png(size, raw):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main():
    os.makedirs(SITE, exist_ok=True)
    for name, size in SIZES.items():
        with open(os.path.join(SITE, name), "wb") as f:
            f.write(png(size, render(size)))
        print(f"wrote site/{name} ({size}x{size})")


if __name__ == "__main__":
    main()
