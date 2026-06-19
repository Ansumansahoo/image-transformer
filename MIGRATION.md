# MIGRATION.md — Phase 0 Inventory & Plan
# image-transformer → Pragmatic Tier Refactor

Generated: Phase 0 code-read pass. Last updated by Claude (Phase 0 commit).

---

## 1. Current Behaviour Inventory

### 1.1 Repository files (main branch, read 2025-06-20)

| File | Size | Role | Status |
|------|------|------|--------|
| `index.html` | 83.4 KB / 1361 lines | Canonical browser tool (vanilla JS, all-in-one) | **KEEP — canonical** |
| `transform_swatches.py` | 23.8 KB / 613 lines | Python CLI v3.0 (server-side, CORS-free) | **KEEP — canonical** |
| `presets.json` | 3.8 KB | 8 builtin + 3 user sample presets | **KEEP — becomes single source** |
| `example.csv` | ~1 KB | 10-row Unsplash URL sample | KEEP |
| `README.md` | ~14 KB | Docs (partially stale) | Rewrite in Phase 5 |
| `index (1).html` | 120 KB / 2255 lines | Older diverged version, uploaded via UI | **DELETE in Phase 4** |
| `image-transformer copy.html` | 40.7 KB / 1226 lines | Another stale copy | **DELETE in Phase 4** |

### 1.2 Browser tool (index.html) — module map

| Section | Lines (approx) | What it does |
|---------|----------------|--------------|
| CSS vars + reset | 1–10 | Dark/light theme, design tokens |
| CSS — layout | 11–260 | App shell, panels, cards, modals |
| HTML — header/action-bar | 261–300 | Buttons, mode toggle, stats |
| HTML — left panel | 301–420 | Input tabs, drop zones, settings panels |
| HTML — right panel | 421–460 | Main drop area, results grid |
| JS — constants | 461–530 | CONCURRENCY=8, SIZE_PRESETS, BUILTIN_PRESETS, SHADOW_DEFS |
| JS — state (st) | 531–560 | Single mutable state object |
| JS — initDOM / D | 561–590 | ID->element map |
| JS — theme | 591–600 | toggleTheme, localStorage |
| JS — setMode | 601–615 | swatch / transform mode switch |
| JS — setInputMode | 616–645 | files/folder/zip/excel/urls tab routing |
| JS — URL input | 646–680 | addSingleUrl, loadUrls |
| JS — pixel math | 681–900 | computeCropBox, centeredCoverBox, detectBoundingBox, extractDominantColor, **renderSwatch**, drawBgOnCtx, applyShapeMask, tracePath, stepDownToFit, downscaleIfNeeded |
| JS — fetch / load | 901–960 | fetchImage, loadImg, _itFetch (BUGGY: itD ref), _itLI |
| JS — file intake | 961–1050 | handleFileInput, handleZip, handleExcelFile, loadSheet, rebuildExcelItems |
| JS — settings | 1051–1200 | initSettings, onBgModeChange, onFormatChange, collectSwatchOpts, itSetFit, itApplyRatio |
| JS — dashboard | 1201–1240 | updateDashboard, updateGoBtn, pause/resume/cancel/retry |
| JS — render | 1241–1290 | render, buildCard, updateCard |
| JS — run pipeline | 1291–1361 | runAll, runSwatches (worker pool), processSwatchItem, runTransform, processTransformItem, downloadAll |
| JS — presets | 1290–1340 | openPresetsModal, applyPreset (fixed in prior commit), savePreset |

### 1.3 Python CLI (transform_swatches.py v3.0) — module map

| Function | Purpose |
|----------|---------|
| `resolve_bg` | Named preset OR hex string → RGBA tuple |
| `make_session` | requests.Session with Retry(respect_retry_after=True, backoff=1.5) |
| `_throttle` | Thread-safe inter-request delay lock |
| `classify_http_error` | 401/403/404/429 → human-readable error |
| `open_image` | PIL open + Image.draft() + ImageOps.exif_transpose |
| `download_image` | fetch with throttle, classify errors |
| `detect_bbox` | 256px thumbnail → ImageChops bbox (fast) |
| `build_base` | Crop+pad to square ONCE per image |
| `apply_shape` | Shape mask (all 7 shapes) |
| `render_size` | build_base.resize(sz) + apply_shape + bg composite |
| `read_input` | xlsx/csv/txt → list of dicts (headerless CSV auto-detect) |
| `process_row` | Single row: download + build_base + emit_sizes |
| `process_folder` | Local directory scan |
| `transform_image` / `process_row_transform` | Image Transformer mode |
| `write_zip` | ZIP_STORED (images already compressed) |
| `write_report` | openpyxl Excel report |

### 1.4 presets.json structure

```json
{
  "user": { "<name>": <PresetObject> },
  "builtin": { "<name>": <PresetObject> }
}
```

**PresetObject fields** (current, pre-schema): shape, sizes (string), ratioW, ratioH,
cropEngine, bgThresh, cropPad, bgMode ("solid"|"transparent"|"gradient"),
bgColor (#hex), bgColor2 (#hex), shadow, borderWidth, borderColor,
format ("image/jpeg"|"image/png"|"image/webp"), quality (0–100), nameTemplate, zipLayout.

**Known issues in presets.json**:
- `bgMode: "solid"` is NOT a valid `<select>` option in the browser (options are white/black/custom/gradient/transparent). Fixed in applyPreset via mapping solid→custom.
- `format: "image/jpeg"` is MIME format, not the select value ("jpeg"). Fixed in applyPreset.
- `bgThresh` key (presets.json) vs `bgThreshold` key (old applyPreset) — resolved in current code.

---

## 2. Known Bugs Status

| # | Bug | Status in current main |
|---|-----|------------------------|
| 1 | Custom bg never paints | **FIXED** (806b0c3): collectSwatchOpts normalizes custom→solid+bgColor; drawBgOnCtx handles white/black/custom |
| 2 | Default 1px border always on | **FIXED** (806b0c3): bw=borderMode==='none'?0:... |
| 3 | Presets mostly inert | **FIXED** (806b0c3): applyPreset applies all 14 fields |
| 4 | CORS proxy dead in Transform | **FIXED** (806b0c3): _itFetch itD→D |
| 5 | EXIF ignored | **FIXED** in Python (2267f74: ImageOps.exif_transpose); browser: ImageBitmap({imageOrientation:'from-image'}) **TODO Phase 3** |
| 6 | ZIP uses DEFLATE | **FIXED** (3d45168 Python, earlier for browser) |
| 7 | Border half-thickness on non-rect shapes | **NOT YET FIXED** — stroke is centered on path edge, clips at canvas boundary on non-rect shapes. **TODO Phase 3** |
| 8 | Sizes silently dropped | **NOT YET FIXED** — collectSwatchOpts drops sizes outside 0<n≤4000 with no user feedback. **TODO Phase 3** |

---

## 3. Module → Target Map (Pragmatic Tier)

```
CURRENT                        TARGET
───────────────────────────────────────────────────────────────────
index.html CSS+HTML            → /web/src/index.html (thin shell)
index.html JS pixel math       → /core-rs/src/ (Rust → WASM)
index.html JS UI/DOM           → /web/src/*.ts  (TypeScript)
index.html JS file intake      → /web/src/intake.ts (JSZip/SheetJS, zero-install)
index.html JS worker pool      → /web/src/worker.ts + pool.ts (OffscreenCanvas)
transform_swatches.py pixel    → calls /core-rs CLI or parity-tested against it
transform_swatches.py fetch    → kept as-is (works, server-side CORS-free)
BUILTIN_PRESETS (JS inline)    → /presets.json (already external, schema-governed)
Python PRESETS dict (missing)  → /presets.json (same file)
schemas/ (missing)             → /schemas/preset.schema.json (new)
fixtures/ (missing)            → /fixtures/ (new, Phase 0)
tests/ (missing)               → /tests/ (new, Phase 0)
.github/workflows/ (missing)   → CI: rust/wasm/tsc/python (new)
README.md (stale)              → rewritten Phase 5
```

---

## 4. Execution Order

### Phase 0 (THIS COMMIT) — Repo skeleton + fixtures + red tests
- [x] Write MIGRATION.md (this file)
- [x] Create directory skeleton: /core-rs, /web, /cli, /schemas, /fixtures, /tests
- [x] presets.json promoted — add schema draft
- [x] Fixture placeholders + parity test harness (red — no Rust yet)
- [x] CI skeleton (.github/workflows/ci.yml)
- [x] STOP for review

### Phase 1 — Rust pixel core + native CLI
- Port detectBoundingBox, buildBase (smart/center/contain/cover/stretch), applyShapeMask
  (all 7 shapes), renderSwatch, drawBg, shadow compositing, dominant-color chip
- Wire cargo CLI (single binary)
- Make parity tests green against current Python output
- Fix bug #7 (border inset), bug #8 (size validation with warning)

### Phase 2 — WASM + Web Worker pool
- wasm-pack build core-rs → /web/pkg
- WorkerPool (OffscreenCanvas), PostMessage protocol
- Replace browser canvas pipeline with WASM calls
- CI: wasm build step

### Phase 3 — TypeScript UI
- Port HTML+JS → TypeScript (discriminated-union options object)
- EXIF fix in browser (bug #5)
- Zero-install local intake preserved (JSZip/SheetJS)
- Schema-driven preset application

### Phase 4 — Unify sources, delete stale files
- Remove BUILTIN_PRESETS from JS (use presets.json at build time)
- Delete `index (1).html` and `image-transformer copy.html`
- Lock Python ↔ Rust parity test

### Phase 5 — README + CI green + final verification
- Rewrite README (accurate flags, architecture diagram)
- CI: all jobs green (rust test, wasm build, tsc --noEmit, python test)
- Smoke test: open built bundle with no server, run 10-row CSV through Python CLI

---

## 5. Open Design Questions (stop before Phase 1 if unresolved)

1. **pyo3 vs subprocess for Python↔Rust**: pyo3 is cleanest but adds a Rust/Python build step; subprocess to the CLI binary is simpler but requires the binary on PATH. **Recommendation**: Phase 1 uses parity tests only (no runtime wiring); Phase 4 decides based on whether test coverage is sufficient.

2. **WASM binary size**: `image` crate + all shape math will likely produce a 300–600 KB WASM blob. Acceptable for GitHub Pages (one-time load, cached). Alternative: use `tiny-skia` only (smaller) and skip the full `image` crate for the browser bundle.

3. **OffscreenCanvas Safari support**: Safari 16.4+ supports OffscreenCanvas. Fallback: main-thread canvas for older Safari (browser worker pool falls back gracefully; keep the old canvas path gated behind a feature check).

4. **presets.json schema version**: Use JSON Schema draft-07 (widest tooling support in both ajv/TS and jsonschema/Python).
