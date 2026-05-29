#!/usr/bin/env python3
"""Terracotta · 赤土 — generate the five 4K wagara wallpapers.

Each wallpaper is a Japanese-constructivist poster built from one traditional
pattern (wagara 和柄), in the charcoal-raku + terracotta palette. The pattern
geometry mirrors the wagara work in skvggor's waka-readme / skvggor.dev.

Usage:  python3 tools/generate-backgrounds.py
Outputs PNGs (3840x2160) into ../backgrounds plus preview/unlock images.
Requires Inkscape for SVG -> PNG rasterization.
"""

import math
import shutil
import subprocess
from pathlib import Path

W, H = 3840, 2160

# ── charcoal raku 炭 base · terracotta clay accents ──
BG       = "#141110"
BG_DEEP  = "#0d0b09"
GHOST    = "#241c16"  # one step above bg — for embossed kanji
SURFACE  = "#211b17"
EARTH_DK = "#3a241a"
EARTH    = "#7a4a2a"
SIENNA   = "#e2885f"  # terracotta-red, AAA (>=7:1) on bg — used for seal/accents
CLAY     = "#e0a878"
CLAY_LT  = "#f0c8a0"
CREAM    = "#f2e6d2"

KANJI = "Noto Sans CJK JP"
SANS  = "Noto Sans"
MONO  = "JetBrainsMono Nerd Font Mono, DejaVu Sans Mono, monospace"

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "backgrounds"


# ────────────────────────── pattern geometry ──────────────────────────
# Faithful to waka-readme's _pattern_* generators; return SVG element strings
# to be wrapped in a stroked, clipped <g>.

def seigaiha(width, height, scale):
    radii = (scale, scale * 2 / 3, scale / 3)
    arcs, row, y = [], 0, 0.0
    while y <= height + scale:
        offset = scale if row % 2 else 0
        x = -scale + offset
        while x <= width + scale:
            for r in radii:
                arcs.append(f"M{x - r:.1f},{y:.1f} A{r:.1f},{r:.1f} 0 0 0 {x + r:.1f},{y:.1f}")
            x += 2 * scale
        row += 1
        y += scale
    return f'<path d="{" ".join(arcs)}"/>'


def shippo(width, height, scale):
    out, y = [], 0.0
    while y <= height + scale:
        x = 0.0
        while x <= width + scale:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{scale:.1f}"/>')
            x += scale
        y += scale
    return "".join(out)


def kikko(width, height, scale):
    out, row, cy = [], 0, 0.0
    hex_w = math.sqrt(3) * scale
    while cy <= height + scale:
        cx = hex_w / 2 if row % 2 else 0.0
        while cx <= width + hex_w:
            pts = [(cx + scale * math.cos(math.radians(90 + 60 * k)),
                    cy + scale * math.sin(math.radians(90 + 60 * k))) for k in range(6)]
            d = " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            out.append(f'<path d="M{d} Z"/>')
            cx += hex_w
        row += 1
        cy += 1.5 * scale
    return "".join(out)


def yabane(width, height, scale):
    out, half, x = [], scale / 2, 0.0
    while x <= width + scale:
        y = -scale
        while y <= height + scale:
            out.append(f'<path d="M{x:.1f},{y:.1f} L{x+half:.1f},{y+half:.1f} L{x+scale:.1f},{y:.1f}"/>')
            out.append(f'<path d="M{x:.1f},{y+half:.1f} L{x+half:.1f},{y+scale:.1f} L{x+scale:.1f},{y+half:.1f}"/>')
            y += scale
        x += scale
    return "".join(out)


def asanoha(width, height, scale):
    delta_y = scale * math.sqrt(3) / 2
    lines = []
    off = lambda j: scale / 2 if j % 2 else 0.0
    mid = lambda p, q: ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)

    def medians(a, b, c):
        for v, o in ((a, mid(b, c)), (b, mid(a, c)), (c, mid(a, b))):
            lines.append(f"M{v[0]:.1f},{v[1]:.1f} L{o[0]:.1f},{o[1]:.1f}")

    rows = int(height / delta_y) + 2
    cols = int(width / scale) + 2
    for j in range(-1, rows):
        low, high = off(j), off(j + 1)
        for i in range(-1, cols):
            medians((i * scale + low, j * delta_y),
                    ((i + 1) * scale + low, j * delta_y),
                    ((i + 0.5) * scale + low, (j + 1) * delta_y))
            medians((i * scale + high, (j + 1) * delta_y),
                    ((i + 1) * scale + high, (j + 1) * delta_y),
                    ((i + 0.5) * scale + high, j * delta_y))
    return f'<path d="{" ".join(lines)}"/>'


# ────────────────────────── composition helpers ──────────────────────────
_defs = []
_clip_n = 0


def clip(shape):
    global _clip_n
    _clip_n += 1
    cid = f"clip{_clip_n}"
    _defs.append(f'<clipPath id="{cid}">{shape}</clipPath>')
    return cid


def textured(cid, geom, color, width, opacity):
    return (f'<g clip-path="url(#{cid})"><g fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" '
            f'opacity="{opacity}">{geom}</g></g>')


def ghost_kanji(ch, x, y, size, fill=GHOST, weight=900, opacity=1.0):
    return (f'<text x="{x}" y="{y}" font-family="{KANJI}" font-weight="{weight}" '
            f'font-size="{size}" fill="{fill}" opacity="{opacity}">{ch}</text>')


def seal(x, y, size, ch):
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{size*0.1:.0f}" fill="{SIENNA}"/>'
            f'<text x="{x+size/2:.0f}" y="{y+size*0.74:.0f}" font-family="{KANJI}" font-weight="900" '
            f'font-size="{size*0.66:.0f}" fill="{BG}" text-anchor="middle">{ch}</text>')


def caption(idx, romaji, jp, meaning):
    bx, by = 170, H - 250
    sp = "".join(c + " " for c in romaji.upper())  # thin-space letter-spacing
    return (
        f'<line x1="{bx}" y1="{by-58}" x2="{bx+520}" y2="{by-58}" stroke="{CLAY}" stroke-width="3" opacity="0.8"/>'
        f'<text x="{bx}" y="{by}" font-family="{SANS}" font-weight="800" font-size="64" '
        f'letter-spacing="6" fill="{CREAM}">{sp}</text>'
        f'<text x="{bx}" y="{by+62}" font-family="{KANJI}" font-weight="500" font-size="46" '
        f'fill="{CLAY}">{jp}  <tspan fill="#cbb295" font-family="{SANS}" font-style="italic">— {meaning}</tspan></text>'
        f'<text x="{W-170}" y="{H-180}" font-family="{MONO}" font-size="34" fill="#b8a084" '
        f'text-anchor="end">terracotta · 赤土 · {idx}/05</text>'
    )


def base_layer(cx, cy):
    # flat charcoal — no gradients (avoids banding and JPEG crackle on smooth ramps).
    # the SVG root already paints a solid BG, so both layers are empty.
    return "", ""


# ────────────────────────── scenes ──────────────────────────

def scene_seigaiha():
    bg, vig = base_layer(0.62, 0.42)
    body = [bg]
    body.append(ghost_kanji("波", 250, 1760, 1500, opacity=1.0))
    # distant sea band
    band = clip(f'<rect x="0" y="{H-460}" width="{W}" height="460"/>')
    body.append(textured(band, seigaiha(W, H, 120), EARTH, 5, 0.18))
    # hinomaru disc of waves
    cx, cy, r = 2440, 880, 760
    disc = clip(f'<circle cx="{cx}" cy="{cy}" r="{r}"/>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{CLAY}"/>')
    body.append(textured(disc, seigaiha(cx + r, cy + r, 70), EARTH_DK, 6, 0.5))
    body.append(vig)
    body.append(seal(W - 360, 210, 150, "青"))
    body.append(caption("01", "seigaiha", "青海波", "blue ocean waves"))
    return "".join(body)


def scene_asanoha():
    bg, vig = base_layer(0.30, 0.5)
    body = [bg]
    body.append(ghost_kanji("麻", 2250, 1760, 1500, opacity=1.0))
    # left lattice column
    col = clip(f'<rect x="0" y="0" width="1180" height="{H}"/>')
    body.append(f'<rect x="0" y="0" width="1180" height="{H}" fill="{SURFACE}" opacity="0.55"/>')
    body.append(textured(col, asanoha(1240, H, 92), CLAY, 3.2, 0.55))
    body.append(f'<line x1="1180" y1="0" x2="1180" y2="{H}" stroke="{SIENNA}" stroke-width="8" opacity="0.85"/>')
    # ring on the right with an asanoha core
    cx, cy = 2600, 1080
    core = clip(f'<circle cx="{cx}" cy="{cy}" r="430"/>')
    body.append(textured(core, asanoha(cx + 480, cy + 480, 74), CLAY_LT, 3, 0.45))
    body.append(f'<circle cx="{cx}" cy="{cy}" r="700" fill="none" stroke="{SIENNA}" stroke-width="16" opacity="0.85"/>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="430" fill="none" stroke="{CLAY}" stroke-width="4" opacity="0.6"/>')
    body.append(vig)
    body.append(seal(W - 360, 210, 150, "葉"))
    body.append(caption("02", "asanoha", "麻の葉", "hemp leaf"))
    return "".join(body)


def scene_shippo():
    bg, vig = base_layer(0.5, 0.42)
    body = [bg]
    body.append(ghost_kanji("宝", 250, 1760, 1500, opacity=1.0))
    # diagonal band of seven-treasures
    cx, cy = W / 2, H / 2
    band = clip(f'<rect x="-200" y="{cy-470}" width="{W+400}" height="940" '
                f'transform="rotate(-28 {cx} {cy})"/>')
    body.append(f'<rect x="-200" y="{cy-470}" width="{W+400}" height="940" transform="rotate(-28 {cx} {cy})" '
                f'fill="{SURFACE}" opacity="0.5"/>')
    body.append(textured(band, shippo(W + 200, H + 200, 78), CLAY, 4.5, 0.5))
    # solid accent disc at a focal point
    body.append(f'<circle cx="2760" cy="760" r="250" fill="{SIENNA}"/>')
    body.append(f'<circle cx="1120" cy="1500" r="120" fill="{CLAY}" opacity="0.9"/>')
    body.append(vig)
    body.append(seal(W - 360, 210, 150, "七"))
    body.append(caption("03", "shippo", "七宝", "seven treasures"))
    return "".join(body)


def scene_kikko():
    bg, vig = base_layer(0.72, 0.32)
    body = [bg]
    body.append(ghost_kanji("亀", 250, 1820, 1500, opacity=1.0))
    # top-right tortoiseshell wedge
    wedge = clip(f'<polygon points="{W*0.42},0 {W},0 {W},{H*0.78}"/>')
    body.append(f'<polygon points="{W*0.42},0 {W},0 {W},{H*0.78}" fill="{SURFACE}" opacity="0.5"/>')
    body.append(textured(wedge, kikko(W, int(H * 0.82), 64), CLAY, 4.5, 0.5))
    body.append(f'<line x1="{W*0.42}" y1="0" x2="{W}" y2="{H*0.78}" stroke="{SIENNA}" stroke-width="12" opacity="0.85"/>')
    # accent hexagon
    s = 200
    pts = [(2950 + s * math.cos(math.radians(90 + 60 * k)), 720 + s * math.sin(math.radians(90 + 60 * k))) for k in range(6)]
    d = " L".join(f"{x:.0f},{y:.0f}" for x, y in pts)
    body.append(f'<path d="M{d} Z" fill="{SIENNA}"/>')
    body.append(vig)
    body.append(seal(330, 250, 150, "甲"))
    body.append(caption("04", "kikko", "亀甲", "tortoiseshell"))
    return "".join(body)


def scene_yabane():
    bg, vig = base_layer(0.4, 0.5)
    body = [bg]
    body.append(ghost_kanji("矢", 2250, 1800, 1500, opacity=1.0))
    # tilted band of arrow feathers, dynamic
    cx, cy = W / 2, H / 2
    band = clip(f'<rect x="-300" y="{cy-560}" width="{W+600}" height="1120" '
                f'transform="rotate(-18 {cx} {cy})"/>')
    body.append(f'<rect x="-300" y="{cy-560}" width="{W+600}" height="1120" transform="rotate(-18 {cx} {cy})" '
                f'fill="{SURFACE}" opacity="0.5"/>')
    body.append(textured(band, yabane(W + 300, H + 300, 74), CLAY, 5, 0.5))
    # bold terracotta arrowhead
    body.append(f'<path d="M3120,560 L3360,920 L3120,860 L2880,920 Z" fill="{SIENNA}"/>')
    body.append(f'<path d="M3120,860 L3120,1480" stroke="{SIENNA}" stroke-width="22" opacity="0.8"/>')
    body.append(vig)
    body.append(seal(330, 250, 150, "矢"))
    body.append(caption("05", "yabane", "矢絣", "arrow fletching"))
    return "".join(body)


SCENES = [
    ("1-seigaiha", scene_seigaiha),
    ("2-asanoha", scene_asanoha),
    ("3-shippo", scene_shippo),
    ("4-kikko", scene_kikko),
    ("5-yabane", scene_yabane),
]


def optimize_png(path):
    """Lossless strip + max deflate. Flat-color posters compress tiny, artifact-free."""
    if shutil.which("magick"):
        subprocess.run(["magick", str(path), "-strip", "-define",
                        "png:compression-level=9", str(path)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def downscale_png(src, dst, width):
    subprocess.run(["magick", str(src), "-resize", f"{width}x", "-strip",
                    "-define", "png:compression-level=9", str(dst)], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def render():
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in list(OUT.glob("*.svg")) + list(OUT.glob("*.jpg")) + list(OUT.glob("*.tmp.png")):
        stale.unlink()

    has_inkscape = shutil.which("inkscape") is not None
    has_magick = shutil.which("magick") is not None

    for name, fn in SCENES:
        global _defs
        _defs = []
        body = fn()
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}"><defs>{"".join(_defs)}</defs>'
               f'<rect width="{W}" height="{H}" fill="{BG}"/>{body}</svg>')
        svg_path = OUT / f"{name}.svg"
        svg_path.write_text(svg)
        if not has_inkscape:
            print(f"  wrote {svg_path.name} (install inkscape to rasterize)")
            continue
        png = OUT / f"{name}.png"
        subprocess.run(["inkscape", str(svg_path), "--export-type=png",
                        f"--export-filename={png}", f"--export-width={W}",
                        f"--export-height={H}"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        svg_path.unlink()
        optimize_png(png)
        print(f"  rendered {png.name} ({png.stat().st_size // 1024} KB)")

    # preview (theme browser) + unlock (Plymouth boot) + preview-unlock
    if has_magick and (OUT / "1-seigaiha.png").exists():
        downscale_png(OUT / "1-seigaiha.png", ROOT / "preview.png", 1920)
        downscale_png(OUT / "2-asanoha.png", ROOT / "unlock.png", 2560)
        downscale_png(ROOT / "unlock.png", ROOT / "preview-unlock.png", 1280)
        print("  wrote preview.png, unlock.png, preview-unlock.png")


if __name__ == "__main__":
    render()
