# core-rs — Rust Pixel Core

**Phase 1 target.** This directory will contain the Rust implementation of the pixel math,
compiled to both a native CLI binary and a WebAssembly module for the browser.

## Status

Phase 0 skeleton only. No Rust code yet.

## Planned structure (Phase 1)

```
core-rs/
  Cargo.toml          # lib + bin targets
  src/
    lib.rs            # Public API: SwatchOptions, render_swatch(), transform_image()
    bbox.rs           # detect_bounding_box() — 256px thumbnail approach
    crop.rs           # build_base() — smart/center/contain/cover/stretch
    shapes.rs         # apply_shape_mask() — all 7 shapes
    render.rs         # render_size() — resize + shape + bg + shadow + border
    color.rs          # extract_dominant_color() — for Color chip shape
    bg.rs             # draw_background() — transparent/white/black/custom/gradient
    shadow.rs         # apply_drop_shadow() — soft/medium/strong/floating
  benches/
    bench_pipeline.rs # criterion benchmarks vs Python
```

## Build commands (Phase 1)

```bash
# Native CLI
cd core-rs && cargo build --release

# WASM (requires wasm-pack)
cd core-rs && wasm-pack build --target web --out-dir ../web/pkg
```

## Design decisions (record here as they are made)

- **Image crate**: use `image` crate (JPEG/PNG/WebP decode/encode) + `imageproc` for
  geometric operations (ellipse, polygon masks).
- **Tiny-skia** for shape mask rasterization (better quality than pure image crate for
  anti-aliased shapes).
- **WASM size target**: < 600 KB gzipped. Exclude features not needed (no GIF, no TIFF
  in the browser path).
- **pyo3 binding**: NOT in Phase 1. Python CLI is parity-tested against Rust CLI
  (subprocess comparison), not runtime-wired. Phase 4 revisits this.
