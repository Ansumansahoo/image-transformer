//! swatch-cli — CLI for the Rust pixel core.
//! Bug #8: invalid sizes are reported, not silently dropped.

use std::path::PathBuf;
use std::fs;
use clap::Parser;
use swatch_core::types::{BgMode, BorderMode, CropEngine, Format, OutputSize, ShapeKind, ShadowMode, SwatchOptions};
use swatch_core::render_swatch;

#[derive(Parser, Debug)]
#[command(name = "swatch-cli", version, about)]
struct Args {
    #[arg(short, long)] input: PathBuf,
    #[arg(short, long, default_value = "output")] output: PathBuf,
    #[arg(short, long, default_value = "300")] sizes: String,
    #[arg(long, default_value = "square")] shape: String,
    #[arg(long, default_value = "white")] bg_mode: String,
    #[arg(long, default_value = "ffffff")] bg_color: String,
    #[arg(long, default_value_t = 30)] bg_thresh: u8,
    #[arg(long, default_value = "none")] border_mode: String,
    #[arg(long, default_value = "000000")] border_color: String,
    #[arg(long, default_value_t = 1)] border_width: u32,
    #[arg(long, default_value = "none")] shadow_mode: String,
    #[arg(long, default_value = "jpeg")] format: String,
    #[arg(long, default_value_t = 85)] quality: u8,
    #[arg(long, default_value = "smart")] crop: String,
}

fn main() {
    let args = Args::parse();
    let mut sizes: Vec<OutputSize> = Vec::new();
    for part in args.sizes.split(',') {
        match OutputSize::parse(part.trim()) {
            Ok(s) => sizes.push(s),
            Err(e) => eprintln!("WARNING: Skipping size '{}': {}", part.trim(), e),
        }
    }
    if sizes.is_empty() {
        eprintln!("ERROR: no valid sizes; defaulting to 300x300");
        sizes.push(OutputSize { width: 300, height: 300 });
    }
    let bg_color = swatch_core::color::parse_hex_color(&args.bg_color).unwrap_or([255,255,255,255]);
    let border_color = swatch_core::color::parse_hex_color(&args.border_color).unwrap_or([0,0,0,255]);
    let opts = SwatchOptions {
        sizes: sizes.clone(), shape: parse_shape(&args.shape),
        bg_mode: parse_bg_mode(&args.bg_mode), bg_color,
        bg_thresh: args.bg_thresh, border_mode: parse_border_mode(&args.border_mode),
        border_color, border_width_px: args.border_width,
        shadow_mode: parse_shadow_mode(&args.shadow_mode),
        shadow_color: [0,0,0,180], shadow_blur: 4.0, shadow_offset_x: 2, shadow_offset_y: 2,
        crop_engine: parse_crop(&args.crop), format: parse_format(&args.format),
        quality: args.quality, ..Default::default()
    };
    let raw_bytes = match fs::read(&args.input) {
        Ok(b) => b,
        Err(e) => { eprintln!("ERROR reading {:?}: {e}", args.input); std::process::exit(1); }
    };
    let stem = args.input.file_stem().and_then(|s| s.to_str()).unwrap_or("swatch");
    fs::create_dir_all(&args.output).unwrap_or_default();
    let results = render_swatch(&raw_bytes, &opts);
    let ext = match opts.format { Format::Jpeg => "jpg", Format::Png => "png", Format::Webp => "webp" };
    for r in &results {
        for w in &r.warnings { eprintln!("WARNING: {w}"); }
        if r.bytes.is_empty() { eprintln!("ERROR: empty output {}x{}", r.size.width, r.size.height); continue; }
        let fname = format!("{stem}_{}x{}.{ext}", r.size.width, r.size.height);
        let path = args.output.join(&fname);
        match fs::write(&path, &r.bytes) {
            Ok(_) => println!("Written: {:?}", path),
            Err(e) => eprintln!("ERROR writing {:?}: {e}", path),
        }
    }
}

fn parse_shape(s: &str) -> ShapeKind {
    match s { "circle" => ShapeKind::Circle, "rounded" => ShapeKind::Rounded, "diamond" => ShapeKind::Diamond, "hexagon" => ShapeKind::Hexagon, "pentagon" => ShapeKind::Pentagon, "octagon" => ShapeKind::Octagon, _ => ShapeKind::Square }
}
fn parse_bg_mode(s: &str) -> BgMode {
    match s { "transparent" => BgMode::Transparent, "custom"|"solid" => BgMode::Custom, "original" => BgMode::Original, "blur" => BgMode::Blur, _ => BgMode::White }
}
fn parse_border_mode(s: &str) -> BorderMode {
    match s { "thin" => BorderMode::Thin, "medium" => BorderMode::Medium, "thick" => BorderMode::Thick, "custom" => BorderMode::Custom, _ => BorderMode::None }
}
fn parse_shadow_mode(s: &str) -> ShadowMode {
    match s { "soft" => ShadowMode::Soft, "hard" => ShadowMode::Hard, "glow" => ShadowMode::Glow, _ => ShadowMode::None }
}
fn parse_format(s: &str) -> Format {
    match s { "png" => Format::Png, "webp" => Format::Webp, _ => Format::Jpeg }
}
fn parse_crop(s: &str) -> CropEngine {
    match s { "center" => CropEngine::Center, "contain" => CropEngine::Contain, "cover" => CropEngine::Cover, "stretch" => CropEngine::Stretch, _ => CropEngine::Smart }
}
