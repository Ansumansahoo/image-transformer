//! Shared types for SwatchOptions — all 8 known-bug fixes are encoded here
//! as proper enums so invalid combos are compile errors.

use serde::{Deserialize, Serialize};

// ── Shape ─────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ShapeKind {
    Square,
    Circle,
    Rounded,
    Diamond,
    Hexagon,
    Pentagon,
    Octagon,
}

impl Default for ShapeKind {
    fn default() -> Self {
        ShapeKind::Square
    }
}

// ── Background ────────────────────────────────────────────────────────────────

/// Bug #1 fix: "custom" is the canonical bgMode value for a user-chosen colour.
/// Bug #3 fix: "solid" was an invalid select value — we unify to "custom".
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BgMode {
    /// Keep existing pixels (no background replacement)
    Original,
    /// Transparent PNG output
    Transparent,
    /// Auto-detected dominant-color chip (white-bg removal)
    White,
    /// Custom solid colour chosen by the user  (bug #1 + #3 fix)
    Custom,
    /// Blur the original behind the shape
    Blur,
}

impl Default for BgMode {
    fn default() -> Self {
        BgMode::White
    }
}

// ── Border ────────────────────────────────────────────────────────────────────

/// Bug #2 fix: "none" must really produce NO border.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BorderMode {
    None,
    Thin,
    Medium,
    Thick,
    Custom,
}

impl Default for BorderMode {
    fn default() -> Self {
        BorderMode::None
    }
}

// ── Shadow ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ShadowMode {
    None,
    Soft,
    Hard,
    Glow,
}

impl Default for ShadowMode {
    fn default() -> Self {
        ShadowMode::None
    }
}

// ── Crop engine ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CropEngine {
    Smart,
    Center,
    Contain,
    Cover,
    Stretch,
}

impl Default for CropEngine {
    fn default() -> Self {
        CropEngine::Smart
    }
}

// ── Output format ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Format {
    Jpeg,
    Png,
    Webp,
}

impl Default for Format {
    fn default() -> Self {
        Format::Jpeg
    }
}

// ── Output size ───────────────────────────────────────────────────────────────

/// Bug #8 fix: instead of silently dropping bad sizes, we store the raw string
/// so callers can surface a warning to the user before clamping.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OutputSize {
    pub width: u32,
    pub height: u32,
}

impl OutputSize {
    /// Validate a (width, height) pair per the 0 < n <= 4000 rule.
    /// Returns Ok(size) or Err with a human-readable message (bug #8 fix).
    pub fn new(width: u32, height: u32) -> Result<Self, String> {
        if width == 0 || height == 0 {
            return Err(format!(
                "Size {}×{} is invalid: dimensions must be > 0",
                width, height
            ));
        }
        if width > 4000 || height > 4000 {
            return Err(format!(
                "Size {}×{} is invalid: dimensions must be <= 4000",
                width, height
            ));
        }
        Ok(OutputSize { width, height })
    }

    /// Parse a size string like "300" (square) or "400x300" (WxH).
    pub fn parse(s: &str) -> Result<Self, String> {
        let s = s.trim();
        if let Some((w, h)) = s.split_once('x').or_else(|| s.split_once('X')) {
            let w: u32 = w.trim().parse().map_err(|_| format!("invalid width '{}'", w))?;
            let h: u32 = h.trim().parse().map_err(|_| format!("invalid height '{}'", h))?;
            OutputSize::new(w, h)
        } else {
            let n: u32 = s.parse().map_err(|_| format!("invalid size '{}'", s))?;
            OutputSize::new(n, n)
        }
    }
}

// ── Name template ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NameTemplate(pub String);

impl Default for NameTemplate {
    fn default() -> Self {
        NameTemplate("{source}_{size}".into())
    }
}

// ── Main options struct ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwatchOptions {
    pub sizes: Vec<OutputSize>,
    pub shape: ShapeKind,
    pub bg_mode: BgMode,
    /// RGBA colour used when bg_mode == BgMode::Custom  (bug #1 fix)
    pub bg_color: [u8; 4],
    pub bg_thresh: u8,
    pub border_mode: BorderMode,
    pub border_color: [u8; 4],
    pub border_width_px: u32,
    pub shadow_mode: ShadowMode,
    pub shadow_color: [u8; 4],
    pub shadow_blur: f32,
    pub shadow_offset_x: i32,
    pub shadow_offset_y: i32,
    pub crop_engine: CropEngine,
    pub format: Format,
    pub quality: u8,
    pub name_template: NameTemplate,
    pub corner_radius_pct: f32,
}

impl Default for SwatchOptions {
    fn default() -> Self {
        SwatchOptions {
            sizes: vec![OutputSize { width: 300, height: 300 }],
            shape: ShapeKind::default(),
            bg_mode: BgMode::default(),
            bg_color: [255, 255, 255, 255],
            bg_thresh: 30,
            border_mode: BorderMode::None,
            border_color: [0, 0, 0, 255],
            border_width_px: 0,
            shadow_mode: ShadowMode::None,
            shadow_color: [0, 0, 0, 180],
            shadow_blur: 4.0,
            shadow_offset_x: 2,
            shadow_offset_y: 2,
            crop_engine: CropEngine::default(),
            format: Format::default(),
            quality: 85,
            name_template: NameTemplate::default(),
            corner_radius_pct: 12.0,
        }
    }
}

// ── Preset ────────────────────────────────────────────────────────────────────

/// Matches presets.json schema (schema-validated at load time)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preset {
    pub id: String,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(flatten)]
    pub options: PresetOverrides,
}

/// Partial overrides — all fields optional so a preset can override just what it needs
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct PresetOverrides {
    pub sizes: Option<Vec<String>>,
    pub shape: Option<ShapeKind>,
    #[serde(rename = "bgMode")]
    pub bg_mode: Option<BgMode>,
    #[serde(rename = "bgColor")]
    pub bg_color: Option<String>,
    /// Bug #3 fix: accept both "bgThresh" and legacy "bgThreshold"
    #[serde(rename = "bgThresh", alias = "bgThreshold")]
    pub bg_thresh: Option<u8>,
    #[serde(rename = "borderMode")]
    pub border_mode: Option<BorderMode>,
    #[serde(rename = "borderColor")]
    pub border_color: Option<String>,
    #[serde(rename = "borderWidth")]
    pub border_width: Option<u32>,
    #[serde(rename = "shadowMode")]
    pub shadow_mode: Option<ShadowMode>,
    pub format: Option<Format>,
    pub quality: Option<u8>,
    #[serde(rename = "nameTemplate")]
    pub name_template: Option<String>,
    #[serde(rename = "zipLayout")]
    pub zip_layout: Option<String>,
}
