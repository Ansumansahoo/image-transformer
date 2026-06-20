//! swatch_core — single source of truth for pixel math
//!
//! Compiles to:
//!   - native (cargo build) for the CLI and Python parity tests
//!   - wasm32-unknown-unknown (wasm-pack build) for the browser worker
//!
//! Public surface: [SwatchOptions], [render_swatch], [transform_image]

pub mod bbox;
pub mod bg;
pub mod border;
pub mod color;
pub mod crop;
pub mod render;
pub mod shadow;
pub mod shapes;
pub mod types;

pub use render::render_swatch;
pub use types::{
    BgMode, BorderMode, CropEngine, Format, NameTemplate, OutputSize, Preset,
    ShapeKind, ShadowMode, SwatchOptions,
};

#[cfg(feature = "wasm")]
pub mod wasm_entry;
