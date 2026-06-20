# core-rs — Rust Pixel Core

**Status: Phase 1 COMPLETE** — CI green.

Single source of truth for all pixel math in Swatch Generator Pro.
Compiles to a native CLI binary and (Phase 2) a WASM module for the browser.

## Modules

| Module | Purpose | Bug fixes |
|--------|---------|-----------|
| `types.rs` | All enums + SwatchOptions | #1, #2, #3, #8 |
| `bbox.rs` | Bounding-box detection (256px thumbnail) | — |
| `crop.rs` | Crop engines (smart/center/contain/cover/stretch) + EXIF | #5 |
| `shapes.rs` | 7 shape masks with anti-aliasing | — |
| `color.rs` | Hex parsing + dominant colour detection | — |
| `bg.rs` | Background compositing (solid/transparent/white/blur) | #1 |
| `shadow.rs` | Drop shadow (soft/hard/glow) | — |
| `border.rs` | Inset border rendering | #2, #7 |
| `render.rs` | Main pipeline orchestrator | all 8 |
| `main.rs` | swatch-cli binary | #8 |
| `wasm_entry.rs` | WASM exports (Phase 2 stub) | — |

## Build

```bash
# Build native CLI
cargo build --release
# Run in target/release/swatch-cli
./target/release/swatch-cli --input photo.jpg --output out/ --sizes 300,600

# Run tests
cargo test
```

## Bug fixes included

1. **#1** Custom BgMode::Custom actually paints the chosen color  
2. **#2** BorderMode::None produces no border  
3. **#3** Preset bgMode "solid" → "custom", bgThreshold alias accepted  
4. **#4** (CORS proxy — browser-layer, not in Rust core)  
5. **#5** EXIF orientation auto-applied in `auto_orient()`  
6. **#6** (ZIP STORE — CLI/browser layer)  
7. **#7** Non-rect shape borders use inset stroke (no half-thickness clip)  
8. **#8** Invalid sizes reported to user via stderr, not silently dropped  
