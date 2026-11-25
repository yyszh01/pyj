"""Draw the pyj icon: a pair of braces on a rounded square.

Writes images/icon.png (256x256, for the VS Code Marketplace / Open VSX) and images/icon.svg
(the same drawing as vectors). Standard library only, so it runs anywhere:

    python3 tools/make_icon.py

The braces are made of quadratic curves and lines; every pixel's coverage comes from its
distance to that outline (anti-aliased), so the PNG and the SVG match.
"""
import math
import os
import struct
import zlib

SIZE = 256
BG = (0x1E, 0x29, 0x3B)          # slate
LEFT = (0x4B, 0x8B, 0xBE)        # blue
RIGHT = (0xFF, 0xD4, 0x3B)       # yellow
RADIUS = 52                      # corner radius of the background
STROKE = 20                      # brace line width

# left brace, in pixels; the right one is its mirror image (x -> SIZE - x)
TOP, BOTTOM, MID = 58, 198, 128
SPINE, TIP, END, BEND = 84, 58, 110, 24
LEFT_BRACE = [
    ("Q", (END, TOP), (SPINE, TOP), (SPINE, TOP + BEND)),
    ("L", (SPINE, TOP + BEND), (SPINE, MID - BEND)),
    ("Q", (SPINE, MID - BEND), (SPINE, MID), (TIP, MID)),
    ("Q", (TIP, MID), (SPINE, MID), (SPINE, MID + BEND)),
    ("L", (SPINE, MID + BEND), (SPINE, BOTTOM - BEND)),
    ("Q", (SPINE, BOTTOM - BEND), (SPINE, BOTTOM), (END, BOTTOM)),
]


def mirror(brace):
    m = lambda p: (SIZE - p[0], p[1])
    return [(kind, *map(m, pts)) for kind, *pts in brace]


def polyline(brace, steps=32):
    """The outline as line segments: quadratic curves are sampled."""
    segs = []
    for kind, *pts in brace:
        if kind == "L":
            segs.append((pts[0], pts[1]))
            continue
        (x0, y0), (cx, cy), (x1, y1) = pts
        prev = (x0, y0)
        for i in range(1, steps + 1):
            t = i / steps
            a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
            p = (a * x0 + b * cx + c * x1, a * y0 + b * cy + c * y1)
            segs.append((prev, p))
            prev = p
    return segs


def seg_dist(px, py, seg):
    (ax, ay), (bx, by) = seg
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    qx, qy = ax + t * dx - px, ay + t * dy - py
    return math.sqrt(qx * qx + qy * qy)


def coverage(d):
    """Signed distance (negative inside) -> pixel coverage, ~1px anti-aliasing."""
    return max(0.0, min(1.0, 0.5 - d))


def rounded_rect_sd(px, py):
    # signed distance to the rounded square that fills the canvas
    half = SIZE / 2
    qx = abs(px - half) - (half - RADIUS)
    qy = abs(py - half) - (half - RADIUS)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - RADIUS


def render():
    braces = [(polyline(LEFT_BRACE), LEFT), (polyline(mirror(LEFT_BRACE)), RIGHT)]
    boxes = []
    for segs, _ in braces:
        xs = [p[0] for s in segs for p in s]
        ys = [p[1] for s in segs for p in s]
        pad = STROKE
        boxes.append((min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad))
    rows = []
    for y in range(SIZE):
        row = bytearray()
        for x in range(SIZE):
            px, py = x + 0.5, y + 0.5
            a = coverage(rounded_rect_sd(px, py))
            r, g, b = BG
            for (segs, col), (x0, x1, y0, y1) in zip(braces, boxes):
                if x0 <= px <= x1 and y0 <= py <= y1:
                    d = min(seg_dist(px, py, s) for s in segs) - STROKE / 2
                    c = coverage(d)
                    if c:
                        r, g, b = (r + (col[0] - r) * c, g + (col[1] - g) * c, b + (col[2] - b) * c)
            row += bytes((round(r), round(g), round(b), round(255 * a)))
        rows.append(bytes(row))
    return rows


def write_png(path, rows):
    raw = b"".join(b"\x00" + r for r in rows)
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)  # 8-bit RGBA
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def svg_path(brace):
    out = []
    for i, (kind, *pts) in enumerate(brace):
        if i == 0:
            out.append("M%g %g" % pts[0])
        if kind == "L":
            out.append("L%g %g" % pts[1])
        else:
            out.append("Q%g %g %g %g" % (*pts[1], *pts[2]))
    return " ".join(out)


def write_svg(path):
    hexc = lambda c: "#%02x%02x%02x" % c
    common = 'fill="none" stroke-width="%d" stroke-linecap="round" stroke-linejoin="round"' % STROKE
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 {s} {s}">\n'
        '  <title>pyj</title>\n'
        '  <rect width="{s}" height="{s}" rx="{r}" fill="{bg}"/>\n'
        '  <path d="{l}" stroke="{lc}" {c}/>\n'
        '  <path d="{rp}" stroke="{rc}" {c}/>\n'
        '</svg>\n'
    ).format(s=SIZE, r=RADIUS, bg=hexc(BG), l=svg_path(LEFT_BRACE), lc=hexc(LEFT),
             rp=svg_path(mirror(LEFT_BRACE)), rc=hexc(RIGHT), c=common)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")
    os.makedirs(out, exist_ok=True)
    write_png(os.path.join(out, "icon.png"), render())
    write_svg(os.path.join(out, "icon.svg"))
    print("wrote images/icon.png and images/icon.svg")
