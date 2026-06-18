#!/usr/bin/env python3
"""
Swatch Generator Pro — Python CLI companion
==========================================
For image URLs from hosts that block browser CORS, or for integrating swatch
generation into ETL pipelines / scheduled batch jobs.

Quick start:
    pip install requests Pillow openpyxl pandas
    python transform_swatches.py products.xlsx --preset shopify-variant --zip

Common flags (all have defaults; see PRESETS below):
    --preset {shopify-variant,amazon-main,wayfair-tile,faire-wholesale,
              wizcommerce-default,color-chip,luxury-pdp,minimal-hexagon}
    --shape {square,circle,rounded,pill,oval,diamond,hexagon,color}
    --sizes 64,128,256,512
    --ratio 1:1              (also 1.7:1, 16:9, 4:3, etc.)
    --crop {smart,center,contain,cover,stretch}
    --bg-thresh 240          (smart crop: pixels brighter → background)
    --crop-pad 8             (smart crop: padding % around product)
    --bg {transparent,solid,gradient}
    --bg-color "#ffffff"
    --bg-color2 "#e6e8ee"   (gradient end color)
    --shadow {none,soft,medium,strong,floating}
    --border-width 0
    --border-color "#cccccc"
    --format {png,jpeg,webp}
    --quality 95
    --name-template "{basename}-{shape}-{size}"
    --zip-layout {by-size,by-product,flat}
    --url-col "Thumbnail URL"
    --sheet "Sheet1"
    --workers 16
    --out ./output
    --zip

Output layout (example --zip-layout by-size):
    output/
      images/
        64/filename.png
        128/filename.png
        256/filename.png
      report.xlsx         (URL-mode only)
      swatches.zip        (when --zip is passed)
"""

import argparse, io, math, os, re, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageDraw, ImageFilter

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS  # Pillow <10

# ─── Built-in presets ─────────────────────────────────────────────────────────
PRESETS = {
    "shopify-variant": dict(
        shape="square", sizes="64,128,256", ratio="1:1", crop="smart",
        bg_thresh=240, crop_pad=8, bg="solid", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="none", border_width=0, border_color="#dddddd",
        format="png", quality=95, name_template="{basename}-{size}", zip_layout="by-size",
    ),
    "amazon-main": dict(
        shape="square", sizes="500,1000,2000", ratio="1:1", crop="smart",
        bg_thresh=245, crop_pad=5, bg="solid", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="none", border_width=0, border_color="#dddddd",
        format="jpeg", quality=92, name_template="{basename}-{size}", zip_layout="by-size",
    ),
    "wayfair-tile": dict(
        shape="square", sizes="100,200,400,800", ratio="1:1", crop="smart",
        bg_thresh=240, crop_pad=10, bg="solid", bg_color="#fafafa", bg_color2="#e6e8ee",
        shadow="soft", border_width=1, border_color="#e6e6e6",
        format="jpeg", quality=90, name_template="{basename}-tile-{size}", zip_layout="by-size",
    ),
    "faire-wholesale": dict(
        shape="rounded", sizes="80,160,320", ratio="1:1", crop="smart",
        bg_thresh=238, crop_pad=12, bg="solid", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="soft", border_width=0, border_color="#dddddd",
        format="png", quality=95, name_template="{basename}-{size}", zip_layout="by-product",
    ),
    "wizcommerce-default": dict(
        shape="square", sizes="128,256,512", ratio="1:1", crop="smart",
        bg_thresh=240, crop_pad=8, bg="solid", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="none", border_width=0, border_color="#dddddd",
        format="jpeg", quality=92, name_template="{basename}-{size}", zip_layout="by-size",
    ),
    "color-chip": dict(
        shape="color", sizes="48,96", ratio="1:1", crop="smart",
        bg_thresh=240, crop_pad=0, bg="transparent", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="none", border_width=1, border_color="#cccccc",
        format="png", quality=100, name_template="{basename}-color-{size}", zip_layout="by-size",
    ),
    "luxury-pdp": dict(
        shape="circle", sizes="64,128,256", ratio="1:1", crop="smart",
        bg_thresh=245, crop_pad=6, bg="transparent", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="soft", border_width=0, border_color="#dddddd",
        format="png", quality=100, name_template="{basename}-circle-{size}", zip_layout="by-size",
    ),
    "minimal-hexagon": dict(
        shape="hexagon", sizes="120,240", ratio="1:1", crop="smart",
        bg_thresh=240, crop_pad=6, bg="transparent", bg_color="#ffffff", bg_color2="#e6e8ee",
        shadow="none", border_width=0, border_color="#dddddd",
        format="png", quality=100, name_template="{basename}-hex-{size}", zip_layout="by-size",
    ),
}

SHADOW_DEFS = {
    "none":     None,
    "soft":     dict(offset=(0, 3),  blur=8,  alpha=46),
    "medium":   dict(offset=(0, 5),  blur=14, alpha=66),
    "strong":   dict(offset=(0, 9),  blur=26, alpha=102),
    "floating": dict(offset=(0, 18), blur=44, alpha=115),
}

IMG_EXTS = re.compile(r"\.(jpe?g|png|webp|gif|bmp|avif|tiff?)$", re.I)
URL_HINTS = re.compile(r"url|image|link|src|photo|thumb|picture|main|primary", re.I)

# ─── Networking ───────────────────────────────────────────────────────────────
def build_session(workers: int) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5,
                  status_forcelist=(500, 502, 503, 504),
                  allowed_methods=("GET",))
    adapter = HTTPAdapter(pool_connections=workers, pool_maxsize=workers * 2, max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": "Mozilla/5.0 SwatchGeneratorPro/2.0",
                       "Accept": "image/*,*/*;q=0.8"})
    return s

def fetch_url(url: str, session: requests.Session, timeout: int = 30) -> bytes:
    r = session.get(url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.content

# ─── Utilities ────────────────────────────────────────────────────────────────
def hex_to_rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))

def parse_sizes(s: str):
    return sorted({int(x) for x in re.split(r"[,\\s]+", s.strip()) if x and x.isdigit() and int(x) > 0})

def parse_ratio(s: str):
    a, b = s.split(":")
    return float(a), float(b)

def filename_from_url(url: str, idx: int) -> str:
    try:
        p = urlparse(url).path
        base = os.path.basename(p) or f"image-{idx+1}"
    except Exception:
        base = f"image-{idx+1}"
    base = re.sub(r"[?#].*$", "", base)
    return base or f"image-{idx+1}"

def detect_url_col(df: pd.DataFrame) -> str:
    named = [c for c in df.columns if URL_HINTS.search(str(c))]
    candidates = named + [c for c in df.columns if c not in named]
    best, best_n = None, 0
    for col in candidates:
        n = df[col].astype(str).str.match(r"^https?://", na=False).sum()
        if n > best_n:
            best, best_n = col, int(n)
    if not best:
        raise SystemExit("No column with http(s):// URLs found.")
    return best

def render_name(template: str, vars_: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(vars_.get(m.group(1), "")), template)

def out_path(layout: str, base: str, size: int, fname: str) -> str:
    if layout == "flat":
        return fname
    if layout == "by-product":
        return f"{base}/{size}.{fname.rsplit('.', 1)[-1]}"
    return f"{size}/{fname}"

# ─── Image processing ─────────────────────────────────────────────────────────
def detect_bounding_box(img: Image.Image, thresh: int):
    scale = min(1.0, 256 / max(img.size))
    sw = max(1, int(img.size[0] * scale))
    sh = max(1, int(img.size[1] * scale))
    small = img.resize((sw, sh), Image.BILINEAR).convert("RGBA")
    px = small.load()
    minx, miny, maxx, maxy = sw, sh, -1, -1
    for y in range(sh):
        for x in range(sw):
            r, g, b, a = px[x, y]
            if a < 16:
                continue
            if r >= thresh and g >= thresh and b >= thresh:
                continue
            if x < minx: minx = x
            if y < miny: miny = y
            if x > maxx: maxx = x
            if y > maxy: maxy = y
    if maxx < 0:
        return (0, 0, img.size[0], img.size[1])
    inv = 1 / scale
    return (int(minx * inv), int(miny * inv), int((maxx + 1) * inv), int((maxy + 1) * inv))

def compute_crop_box(img: Image.Image, args):
    W, H = img.size
    rw, rh = parse_ratio(args.ratio)
    tR = rw / rh
    if args.crop == "stretch":
        return (0, 0, W, H, "stretch")
    if args.crop == "contain":
        return (0, 0, W, H, "contain")
    if args.crop == "cover":
        return centered_cover(W, H, tR) + ("cover",)
    if args.crop == "smart":
        x0, y0, x1, y1 = detect_bounding_box(img, args.bg_thresh)
        bw, bh = x1 - x0, y1 - y0
        cx, cy = x0 + bw / 2, y0 + bh / 2
        pad = args.crop_pad / 100.0
        w = bw * (1 + pad * 2)
        h = bh * (1 + pad * 2)
        if w / max(h, 1) > tR:
            h = w / tR
        else:
            w = h * tR
        x = cx - w / 2
        y = cy - h / 2
        x = max(0.0, min(W - w, x))
        y = max(0.0, min(H - h, y))
        if w > W or h > H:
            return centered_cover(W, H, tR) + ("cover",)
        return (x, y, x + w, y + h, "cover")
    return centered_cover(W, H, tR) + ("cover",)

def centered_cover(W, H, tR):
    sR = W / H
    if sR > tR:
        sh = H; sw = H * tR; sx = (W - sw) / 2; sy = 0.0
    else:
        sw = W; sh = W / tR; sx = 0.0; sy = (H - sh) / 2
    return (sx, sy, sx + sw, sy + sh)

def extract_dominant(img: Image.Image, box, thresh: int):
    crop = img.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3]))).convert("RGBA")
    crop.thumbnail((64, 64), RESAMPLE)
    px = crop.load()
    w, h = crop.size
    buckets = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 32:
                continue
            if r >= thresh and g >= thresh and b >= thresh:
                continue
            key = (r >> 4, g >> 4, b >> 4)
            buckets[key] = buckets.get(key, 0) + 1
    if not buckets:
        return (128, 128, 128)
    top = max(buckets, key=buckets.__getitem__)
    tr, tg, tb = top[0] << 4, top[1] << 4, top[2] << 4
    sr = sg = sb = n = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 32:
                continue
            if (r & 0xF0) == tr and (g & 0xF0) == tg and (b & 0xF0) == tb:
                sr += r; sg += g; sb += b; n += 1
    if n == 0:
        return (tr | 8, tg | 8, tb | 8)
    return (sr // n, sg // n, sb // n)

def make_shape_mask(size, shape) -> Image.Image:
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if shape in ("square", "color"):
        d.rectangle((0, 0, w - 1, h - 1), fill=255)
    elif shape in ("circle",):
        d.ellipse((0, 0, w - 1, h - 1), fill=255)
    elif shape == "oval":
        d.ellipse((0, 0, w - 1, h - 1), fill=255)
    elif shape == "rounded":
        r = max(2, int(min(w, h) * 0.15))
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    elif shape == "pill":
        r = min(w, h) // 2
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    elif shape == "diamond":
        d.polygon([(w // 2, 0), (w - 1, h // 2), (w // 2, h - 1), (0, h // 2)], fill=255)
    elif shape == "hexagon":
        cx, cy = w / 2, h / 2
        pts = [(cx + math.cos(math.pi / 3 * i - math.pi / 2) * (w / 2),
                cy + math.sin(math.pi / 3 * i - math.pi / 2) * (h / 2))
               for i in range(6)]
        d.polygon(pts, fill=255)
    return m

def render_swatch(img: Image.Image, box, base_size: int, args, solid_color=None) -> bytes:
    rw, rh = parse_ratio(args.ratio)
    if rw >= rh:
        out_w = base_size
        out_h = max(1, round(base_size * rh / rw))
    else:
        out_h = base_size
        out_w = max(1, round(base_size * rw / rh))

    bw = max(0, int(args.border_width or 0))
    inner_w = max(1, out_w - bw * 2)
    inner_h = max(1, out_h - bw * 2)

    # ── Build inner content ──
    if args.shape == "color":
        inner = Image.new("RGBA", (inner_w, inner_h), solid_color + (255,))
    else:
        x0, y0, x1, y1, mode = box
        crop = img.crop((int(x0), int(y0), int(x1), int(y1)))
        if mode == "contain":
            cR = crop.size[0] / max(crop.size[1], 1)
            tR2 = inner_w / max(inner_h, 1)
            if cR > tR2:
                dw = inner_w; dh = max(1, round(inner_w / cR))
            else:
                dh = inner_h; dw = max(1, round(inner_h * cR))
            bg = Image.new("RGBA", (inner_w, inner_h), (0, 0, 0, 0))
            if args.bg == "solid":
                bg = Image.new("RGBA", (inner_w, inner_h), hex_to_rgb(args.bg_color) + (255,))
            scaled = crop.resize((dw, dh), RESAMPLE)
            if scaled.mode != "RGBA":
                scaled = scaled.convert("RGBA")
            bg.paste(scaled, ((inner_w - dw) // 2, (inner_h - dh) // 2), scaled)
            inner = bg
        elif mode == "stretch":
            scaled = crop.resize((inner_w, inner_h), RESAMPLE)
            inner = scaled.convert("RGBA") if scaled.mode != "RGBA" else scaled
        else:  # cover
            # Iterative step-down for LANCZOS quality
            cur = crop
            while max(cur.size) // 2 > max(inner_w, inner_h):
                cur = cur.resize((max(1, cur.size[0] // 2), max(1, cur.size[1] // 2)), RESAMPLE)
            scaled = cur.resize((inner_w, inner_h), RESAMPLE)
            inner = scaled.convert("RGBA") if scaled.mode != "RGBA" else scaled

    # ── Shape mask ──
    if args.shape not in ("square", "color"):
        mask = make_shape_mask((inner_w, inner_h), args.shape)
        masked = Image.new("RGBA", (inner_w, inner_h), (0, 0, 0, 0))
        masked.paste(inner, (0, 0), mask)
        inner = masked

    # ── Outer canvas ──
    out = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    if args.bg == "solid":
        out.paste(Image.new("RGBA", (out_w, out_h), hex_to_rgb(args.bg_color) + (255,)))
    elif args.bg == "gradient":
        c1 = hex_to_rgb(args.bg_color)
        c2 = hex_to_rgb(args.bg_color2)
        grad = Image.new("RGB", (out_w, out_h))
        gpx = grad.load()
        for y in range(out_h):
            for x in range(out_w):
                t = (x + y) / max(1, out_w + out_h - 2)
                gpx[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        out.paste(grad.convert("RGBA"))

    # ── Shadow ──
    sh_def = SHADOW_DEFS.get(args.shadow)
    if sh_def:
        if args.shape in ("square", "color"):
            sh_alpha = Image.new("L", (inner_w, inner_h), sh_def["alpha"])
        else:
            sh_alpha = make_shape_mask((inner_w, inner_h), args.shape)
            sh_alpha = sh_alpha.point(lambda v: int(v * sh_def["alpha"] / 255))
        shadow_layer = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        shadow_img = Image.new("RGBA", (inner_w, inner_h), (0, 0, 0, 0))
        shadow_img.putalpha(sh_alpha)
        ox2, oy2 = sh_def["offset"]
        shadow_layer.paste(shadow_img, (bw + ox2, bw + oy2), shadow_img)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=sh_def["blur"]))
        out = Image.alpha_composite(out, shadow_layer)

    # ── Composite inner ──
    out.paste(inner, (bw, bw), inner)

    # ── Border ──
    if bw > 0:
        bd_layer = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bd_layer)
        bc = hex_to_rgb(args.border_color or "#cccccc") + (255,)
        h2 = bw // 2
        if args.shape in ("square", "color"):
            bd.rectangle((h2, h2, out_w - h2 - 1, out_h - h2 - 1), outline=bc, width=bw)
        elif args.shape in ("circle",):
            bd.ellipse((h2, h2, out_w - h2 - 1, out_h - h2 - 1), outline=bc, width=bw)
        elif args.shape == "oval":
            bd.ellipse((h2, h2, out_w - h2 - 1, out_h - h2 - 1), outline=bc, width=bw)
        elif args.shape == "rounded":
            r = max(2, int(min(out_w, out_h) * 0.15))
            bd.rounded_rectangle((h2, h2, out_w - h2 - 1, out_h - h2 - 1), radius=r, outline=bc, width=bw)
        elif args.shape == "pill":
            r = min(out_w, out_h) // 2
            bd.rounded_rectangle((h2, h2, out_w - h2 - 1, out_h - h2 - 1), radius=r, outline=bc, width=bw)
        elif args.shape == "diamond":
            pts = [(out_w // 2, h2), (out_w - h2, out_h // 2),
                   (out_w // 2, out_h - h2), (h2, out_h // 2)]
            bd.polygon(pts, outline=bc)
        elif args.shape == "hexagon":
            cx, cy = out_w / 2, out_h / 2
            pts = [(cx + math.cos(math.pi / 3 * i - math.pi / 2) * (out_w / 2 - h2),
                    cy + math.sin(math.pi / 3 * i - math.pi / 2) * (out_h / 2 - h2))
                   for i in range(6)]
            bd.polygon(pts, outline=bc)
        out = Image.alpha_composite(out, bd_layer)

    # ── Encode ──
    fmt = args.format.lower()
    pil_fmt = {"jpeg": "JPEG", "jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[fmt]
    if pil_fmt == "JPEG":
        bg_rgb = hex_to_rgb(args.bg_color or "#ffffff")
        flat = Image.new("RGB", out.size, bg_rgb)
        flat.paste(out, mask=out)
        out = flat
    buf = io.BytesIO()
    kw = {}
    if pil_fmt in ("JPEG", "WEBP"):
        kw["quality"] = int(args.quality)
        if pil_fmt == "JPEG":
            kw["optimize"] = True
            kw["progressive"] = True
    out.save(buf, format=pil_fmt, **kw)
    return buf.getvalue()

# ─── Worker ───────────────────────────────────────────────────────────────────
def process_one(idx, src, is_local, args, sizes, session, img_out):
    rec = dict(idx=idx, src=src, status="skipped", error="",
               src_w="", src_h="", outputs={})
    try:
        if is_local:
            data = Path(src).read_bytes()
        else:
            data = fetch_url(src, session)
        img = Image.open(io.BytesIO(data))
        img.load()
        if img.mode == "P":
            img = img.convert("RGBA")
        rec["src_w"], rec["src_h"] = img.size
        box = compute_crop_box(img, args)
        solid = extract_dominant(img, box, args.bg_thresh) if args.shape == "color" else None
        if is_local:
            base = Path(src).stem
        else:
            raw = filename_from_url(src, idx)
            base = re.sub(r"\.[^.]+$", "", raw)
        ext = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp"}[args.format.lower()]
        for i, sz in enumerate(sizes):
            blob = render_swatch(img, box, sz, args, solid)
            fname = render_name(args.name_template, dict(
                basename=base, shape=args.shape, size=sz, index=i + 1)) + "." + ext
            rel = out_path(args.zip_layout, base, sz, fname)
            dest = img_out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            rec["outputs"][sz] = rel
        rec["status"] = "done"
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = str(e)[:250]
    return rec

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Swatch Generator Pro — bulk swatches from image URLs or local files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input", help="Excel/CSV file of URLs  —OR—  directory of images")
    p.add_argument("--preset", choices=list(PRESETS))
    p.add_argument("--shape", choices=["square","circle","rounded","pill","oval","diamond","hexagon","color"])
    p.add_argument("--sizes", default=None)
    p.add_argument("--ratio", default=None)
    p.add_argument("--crop", choices=["smart","center","contain","cover","stretch"])
    p.add_argument("--bg-thresh", type=int, default=None, dest="bg_thresh")
    p.add_argument("--crop-pad", type=int, default=None, dest="crop_pad")
    p.add_argument("--bg", choices=["transparent","solid","gradient"])
    p.add_argument("--bg-color", default=None, dest="bg_color")
    p.add_argument("--bg-color2", default=None, dest="bg_color2")
    p.add_argument("--shadow", choices=list(SHADOW_DEFS))
    p.add_argument("--border-width", type=int, default=None, dest="border_width")
    p.add_argument("--border-color", default=None, dest="border_color")
    p.add_argument("--format", choices=["jpeg","png","webp"])
    p.add_argument("--quality", type=int, default=None)
    p.add_argument("--name-template", default=None, dest="name_template")
    p.add_argument("--zip-layout", choices=["by-size","by-product","flat"], dest="zip_layout")
    p.add_argument("--sheet", default=None)
    p.add_argument("--url-col", default=None, dest="url_col")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--out", default="./output")
    p.add_argument("--zip", action="store_true")
    p.add_argument("--timeout", type=int, default=30)
    args = p.parse_args()

    # Merge defaults ← preset ← explicit flags
    defaults = dict(shape="square", sizes="128,256", ratio="1:1", crop="smart",
                    bg_thresh=240, crop_pad=8, bg="solid", bg_color="#ffffff",
                    bg_color2="#e6e8ee", shadow="none", border_width=0,
                    border_color="#cccccc", format="png", quality=95,
                    name_template="{basename}-{size}", zip_layout="by-size")
    if args.preset:
        defaults.update(PRESETS[args.preset])
    for k, v in defaults.items():
        if getattr(args, k, None) is None:
            setattr(args, k, v)

    sizes = parse_sizes(args.sizes)
    print(f"[SwatchPro] preset={args.preset or '(custom)'}  shape={args.shape}  "
          f"sizes={sizes}  ratio={args.ratio}")
    print(f"            crop={args.crop}  bg={args.bg}/{args.bg_color}  "
          f"shadow={args.shadow}  border={args.border_width}px  format={args.format} q{args.quality}")

    out_root = Path(args.out)
    img_out = out_root / "images"
    img_out.mkdir(parents=True, exist_ok=True)

    inp = Path(args.input)
    is_dir = inp.is_dir()
    session = None if is_dir else build_session(args.workers)

    if is_dir:
        files = sorted([f for f in inp.rglob("*") if f.is_file() and IMG_EXTS.search(f.name)])
        print(f"[SwatchPro] {len(files)} images found in {inp}")
        tasks = [(i, str(f), True) for i, f in enumerate(files)]
        df_report = None
    else:
        if inp.suffix.lower() == ".csv":
            df = pd.read_csv(inp, dtype=str).fillna("")
        else:
            df = pd.read_excel(inp, sheet_name=args.sheet or 0, dtype=str).fillna("")
        print(f"[SwatchPro] {len(df)} rows loaded from {inp.name}")
        url_col = args.url_col or detect_url_col(df)
        print(f"            URL column: \"{url_col}\"")
        urls = df[url_col].astype(str).str.strip().tolist()
        tasks = [(i, u, False) for i, u in enumerate(urls)]
        df_report = df.copy()

    t0 = time.time()
    results = [None] * len(tasks)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process_one, i, src, is_local, args, sizes, session, img_out): i
                for i, src, is_local in tasks}
        done_n = 0
        for fut in as_completed(futs):
            i = futs[fut]
            results[i] = fut.result()
            done_n += 1
            if done_n % max(1, len(tasks) // 20) == 0 or done_n == len(tasks):
                ok = sum(1 for r in results if r and r["status"] == "done")
                err = sum(1 for r in results if r and r["status"] == "error")
                rate = done_n / max(time.time() - t0, 1e-3)
                print(f"  {done_n}/{len(tasks)}  ok={ok}  err={err}  {rate:.1f} img/s")

    ok = sum(1 for r in results if r and r["status"] == "done")
    err = sum(1 for r in results if r and r["status"] == "error")
    print(f"[SwatchPro] Done: {ok} ok  {err} errors  in {time.time()-t0:.1f}s")

    # Report
    if df_report is not None:
        size_cols = [f"swatch_{s}" for s in sizes]
        extra_cols = ["status", "error", "shape", "crop_engine", "source_width", "source_height"] + size_cols
        for col in extra_cols:
            df_report[col] = ""
        for r in results:
            if not r:
                continue
            i = r["idx"]
            df_report.at[i, "status"] = r["status"]
            df_report.at[i, "error"] = r["error"]
            df_report.at[i, "shape"] = args.shape
            df_report.at[i, "crop_engine"] = args.crop
            df_report.at[i, "source_width"] = r["src_w"]
            df_report.at[i, "source_height"] = r["src_h"]
            for s in sizes:
                df_report.at[i, f"swatch_{s}"] = r["outputs"].get(s, "")
        report_path = out_root / "report.xlsx"
        df_report.to_excel(report_path, index=False)
        print(f"[SwatchPro] Report: {report_path}")

    if args.zip:
        zpath = out_root / "swatches.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in img_out.rglob("*"):
                if f.is_file():
                    z.write(f, arcname=str(f.relative_to(img_out)))
            if (out_root / "report.xlsx").exists():
                z.write(out_root / "report.xlsx", arcname="report.xlsx")
        print(f"[SwatchPro] Bundle: {zpath}")

if __name__ == "__main__":
    main()
