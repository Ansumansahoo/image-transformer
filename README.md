# Swatch Generator Pro

> Bulk product-swatch generation for e-commerce catalogs.  
> Shopify · Amazon · Wayfair · Faire · WizCommerce · BigCommerce · Magento · WooCommerce · PIMs · ERPs · Marketplaces  
> Pairs a **fully-offline browser tool** with a **Python CLI** for CORS-blocked hosts.

---

## What's in this folder

| File | Purpose |
|---|---|
| `index.html` | Browser tool. Open in any modern browser — no install, no server. |
| `transform_swatches.py` | Python CLI for CORS-blocked URL hosts, ETL pipelines, or directory batches. |
| `presets.json` | 8 built-in + 3 sample user presets. Import via the browser tool's Presets panel. |
| `example.csv` | 10-row sample CSV illustrating the URL-column format both tools accept. |
| `README.md` | This file. |

---

## Browser Tool — Quick Start

1. **Open** `index.html` in Chrome, Edge, Safari, or Firefox.  
   *No server required. Everything runs in your browser.*

2. **Pick an input mode** (top of sidebar):
   - **Files** — drag-drop or click-to-browse any number of images (jpg, png, webp, gif, bmp, avif)
   - **Folder** — pick a directory; all images inside load recursively (Chrome/Edge/Safari)
   - **ZIP** — drop a `.zip` archive; every image at any depth is extracted automatically
   - **Excel/CSV** — drop `.xlsx`, `.xls`, or `.csv`; the tool auto-detects the URL column and sheet

3. **Choose a shape:**
   Square · Circle · Rounded · Pill · Oval · Diamond · Hexagon · Color chip

4. **Set sizes** — type comma-separated px values or click the preset pills (16 → 1200).

5. **Set aspect ratio** — click a ratio pill (1:1, 4:3, 16:9 …) or enter custom W/H.

6. **Tune crop, background, shadow, border** in the sidebar.

7. Click **▶ Generate Swatches**. Watch the live progress dashboard for speed & ETA.

8. Click **⬇ Download All (.zip)** to get everything, or use the card-level **Download** button for a single product.

---

## Inputs Supported

### Local Files
Drag-drop or click-browse: `jpg`, `jpeg`, `png`, `webp`, `gif`, `bmp`, `avif`, `tiff`

### Folder Upload
Chrome/Edge/Safari support the `webkitdirectory` API. All images inside the folder (and its subfolders) are loaded automatically.

### ZIP Archive
Drop any `.zip`. The tool uses JSZip to extract images at any depth. Folder paths are stripped; original filenames are preserved.

### Excel / CSV of URLs
Drop `.xlsx`, `.xls`, or `.csv`. The tool:
- Reads all sheets and picks the one with the most image URLs
- Auto-detects the URL column (looks for `image`, `url`, `link`, `src`, `photo`, `thumb`, `picture`, `main`, `primary` in column names)
- Lets you override both sheet and column via dropdowns
- Generates an Excel report (original rows + status + output paths) downloadable alongside the ZIP

---

## Outputs

| Output | How to get it |
|---|---|
| Combined ZIP | **⬇ Download All (.zip)** button |
| Per-product ZIP | **⬇ Download** button on each card |
| Excel report | **📊 Excel Report** button (URL/Excel mode only) |

### ZIP layouts (set in sidebar)
| Layout | Structure |
|---|---|
| By size | `64/product-64.png`, `128/product-128.png`, … |
| By product | `product/64.png`, `product/128.png`, … |
| Flat | `product-64.png`, `product-128.png`, … (everything at root) |

---

## Crop Engines

| Engine | Best for |
|---|---|
| **Smart** *(default)* | On-white product photography. Detects the product area, ignores white/near-white background. Tunable via BG Threshold and Crop Padding sliders. |
| **Center** | Products that fill the frame; fastest, no detection. |
| **Contain** | Fit the whole image inside the swatch; pads unused area with your chosen background. |
| **Cover** | Geometric center crop to fill the ratio exactly. |
| **Stretch** | Squash to exact dimensions (rarely recommended). |

---

## Shapes

| Shape | Notes |
|---|---|
| Square | Standard rectangular crop. |
| Circle | Circular mask. Use PNG or WebP for transparent corners. |
| Rounded | Rounded-corner rectangle (~15% radius). |
| Pill | Fully rounded ends. Looks best on wide ratios. |
| Oval | Ellipse mask. |
| Diamond | 45° rotated square. |
| Hexagon | Six-sided polygon — popular for material/tile swatches. |
| Color chip | Extracts the dominant non-white color and fills a flat solid swatch. |

---

## File Naming Template

Default: `{basename}-{size}`

Available placeholders:

| Placeholder | Value |
|---|---|
| `{basename}` | Source filename without extension |
| `{shape}` | Active shape name (square, circle, …) |
| `{size}` | Output size in px |
| `{index}` | 1-based index within the sizes list |

Examples:
- `{basename}-{size}` → `red-shirt-128.png`
- `{basename}-{shape}-{size}` → `red-shirt-circle-128.png`
- `SKU_{basename}_{index}` → `SKU_red-shirt_2.png`

---

## Presets

Built-in presets (applied from the **⚙ Presets** panel):

| Preset | Shape | Sizes | Format | Notes |
|---|---|---|---|---|
| Shopify variant | Square | 64, 128, 256 | PNG | Standard variant swatch sizes |
| Amazon main image | Square | 500, 1000, 2000 | JPEG | White background, q92 |
| Wayfair tile | Square | 100, 200, 400, 800 | JPEG | Soft shadow, 1px border |
| Faire wholesale | Rounded | 80, 160, 320 | PNG | Generous padding |
| WizCommerce default | Square | 128, 256, 512 | JPEG | Standard catalog sizes |
| Color chip | Color | 48, 96 | PNG | Dominant-color extraction |
| Luxury PDP | Circle | 64, 128, 256 | PNG | Transparent bg, soft shadow |
| Minimal hexagon | Hexagon | 120, 240 | PNG | Transparent bg, no shadow |

**Saving your own presets:** Tune all settings → click **⚙ Presets** → type a name → **Save Current**.  
Presets are stored in `localStorage` and survive page reloads.

**Sharing presets:** Export to JSON → share the file → Import on another machine.

---

## Performance

- **8-way concurrency** — processes up to 8 images simultaneously.
- **Iterative half-step downscaling** — approximates LANCZOS quality while staying in-browser.
- **`createImageBitmap()`** used when available — off-thread image decode on Chrome/Edge.
- **Aggressive object URL cleanup** — `URL.revokeObjectURL()` called immediately after each transform; memory stays flat across large batches.
- **Pause / Resume / Cancel / Retry-failed** — full control over the processing queue.
- Tested on batches of **300+ images** in a single session.

---

## Python CLI — `transform_swatches.py`

Use the Python CLI when:
- Image URLs are on a CORS-blocked host (common with internal CDNs, Magento, private S3)
- You want to integrate swatch generation into a nightly ETL / cron job
- You have a directory of images to batch-process server-side

### Setup

```bash
pip install requests Pillow openpyxl pandas
# or
pip3 install --break-system-packages requests Pillow openpyxl pandas
```

### Usage

```bash
# From an Excel/CSV of URLs, Shopify-style swatches:
python transform_swatches.py products.xlsx --preset shopify-variant --zip --out ./out

# From a local directory of images:
python transform_swatches.py ./photos \
  --shape circle --sizes 64,128,256 --ratio 1:1 \
  --crop smart --bg transparent --shadow soft \
  --format png --quality 100 --workers 16 --zip --out ./out

# Override individual flags on top of a preset:
python transform_swatches.py products.xlsx \
  --preset amazon-main --shape rounded --sizes 200,400,800

# Amazon listing images from a CSV:
python transform_swatches.py catalog.csv \
  --url-col "Main Image URL" --preset amazon-main \
  --workers 32 --zip --out ./amazon-swatches
```

### All Flags

```
--preset {shopify-variant, amazon-main, wayfair-tile, faire-wholesale,
          wizcommerce-default, color-chip, luxury-pdp, minimal-hexagon}

--shape   {square, circle, rounded, pill, oval, diamond, hexagon, color}
--sizes   64,128,256,512
--ratio   1:1            (also 4:3, 16:9, 1.7:1, 2:3, 9:16, etc.)
--crop    {smart, center, contain, cover, stretch}
--bg-thresh 240          (smart: pixels brighter than this → background)
--crop-pad  8            (smart: padding % around detected product)
--bg      {transparent, solid, gradient}
--bg-color  "#ffffff"
--bg-color2 "#e6e8ee"   (gradient end color)
--shadow  {none, soft, medium, strong, floating}
--border-width 0
--border-color "#cccccc"
--format  {png, jpeg, webp}
--quality 95
--name-template "{basename}-{shape}-{size}"
--zip-layout    {by-size, by-product, flat}
--sheet   "Sheet1"       (multi-sheet workbooks)
--url-col "Thumbnail URL" (override column auto-detect)
--workers 16
--timeout 30             (HTTP timeout in seconds)
--out     ./output
--zip                    (bundle output into a single ZIP)
```

### Output Structure

```
output/
  images/
    64/filename.png        ← by-size layout
    128/filename.png
    256/filename.png
  report.xlsx              ← URL/Excel mode: input rows + status + swatch paths
  swatches.zip             ← when --zip is passed
```

### Error Handling

| Scenario | Behaviour |
|---|---|
| Broken / unreachable URL | Marked `error` in report; batch continues |
| CORS-blocked URL (browser) | Enable proxy or use Python CLI |
| Corrupt / unsupported image | Skipped with error logged |
| Large files (> 50 MB) | Processed normally; browser may slow on very large total sizes |
| Duplicate filenames in ZIP | Deduplicated with `-2`, `-3` suffix |
| Network timeout | Retried 3× with exponential backoff |

---

## Extending the Tool

The browser tool is organized in clearly labeled sections inside `index.html`'s `<script>` block:

1. **Constants** — concurrency, size presets, shadow definitions, built-in presets
2. **State** — single mutable object; all async workers read/write through it
3. **DOM lookups** — all IDs mapped once at startup
4. **Theme** — dark/light toggle, persisted to localStorage
5. **UI helpers** — size pills, ratio pills, shape grid, format/BG wiring
6. **File intake** — files, folder, ZIP (JSZip), Excel (SheetJS)
7. **Settings** — `getSettings()` / `applyPresetValues()`
8. **Preset management** — localStorage CRUD, import/export JSON
9. **Render** — dashboard stats, results grid, live before/after preview
10. **Processing pipeline** — bounded 8-way concurrency, pause/resume/cancel
11. **Per-image transform** — crop box, dominant color, canvas rendering, shape mask
12. **Download** — per-item ZIP, combined ZIP, Excel report

### Adding AI background removal

Install an ONNX model (e.g., RMBG-1.4 via `ort` Web) and add:
```js
async function removeBackground(imgBitmap) { /* your ONNX inference here */ }
```
Then call it in `generateSwatches()` before `computeCropBox()`. The rest of the pipeline needs no changes.

### Adding a new shape

**Browser:** extend `tracePath()` in the script block and add a button to `#shapeGrid`.  
**Python:** extend `make_shape_mask()` in `transform_swatches.py`.

### Adding a new built-in preset

**Browser:** append to the `BUILTIN_PRESETS` object near the top of the script.  
**Python:** append to the `PRESETS` dict near the top of `transform_swatches.py`.

---

## Dependencies

### Browser tool
| Library | Version | CDN | Purpose |
|---|---|---|---|
| JSZip | 3.10.1 | jsDelivr | ZIP creation and reading |
| SheetJS (xlsx) | 0.18.5 | jsDelivr | Excel/CSV reading and writing |

Both load from CDN. For fully offline use, download the minified files and update the `<script>` `src` attributes to relative paths.

### Python CLI
```
requests >= 2.28
Pillow >= 9.0
openpyxl >= 3.0
pandas >= 1.5
```

---

## License

MIT — free to use, modify, and distribute. Attribution appreciated.

---

*Built for eCommerce catalog teams who need to generate thousands of professional swatches automatically, without paid services or cloud dependencies.*
