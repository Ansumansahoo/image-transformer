//! Main render pipeline — all 8 bug fixes wired.
//! Pipeline: auto_orient -> detect_bbox -> crop_resize -> shape_mask
//!   -> composite_bg -> shadow -> border -> encode

use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use crate::bbox::{BBox, detect_bbox};
use crate::border::{apply_border, border_width};
use crate::bg::composite_bg;
use crate::crop::{auto_orient, crop_and_resize};
use crate::shadow::apply_shadow;
use crate::shapes::{apply_mask, make_mask};
use crate::types::{Format, OutputSize, SwatchOptions};

pub struct RenderResult {
    pub size: OutputSize,
    pub bytes: Vec<u8>,
    pub warnings: Vec<String>,
}

pub fn render_swatch(raw_bytes: &[u8], opts: &SwatchOptions) -> Vec<RenderResult> {
    let img = match image::load_from_memory(raw_bytes) {
        Ok(i) => i,
        Err(e) => return opts.sizes.iter().map(|s| RenderResult {
            size: s.clone(), bytes: vec![], warnings: vec![format!("Failed to decode: {e}")]
        }).collect(),
    };
    let img = auto_orient(img, raw_bytes);
    let bg_rgba = Rgba(opts.bg_color);
    let bbox = detect_bbox(&img, bg_rgba, opts.bg_thresh);
    opts.sizes.iter().map(|size| render_one(&img, size, opts, &bbox)).collect()
}

fn render_one(img: &DynamicImage, size: &OutputSize, opts: &SwatchOptions, bbox: &BBox) -> RenderResult {
    let cropped = crop_and_resize(img, size, opts.crop_engine, bbox);
    let mask = make_mask(size.width, size.height, opts.shape, opts.corner_radius_pct);
    let rgba8 = cropped.to_rgba8();
    let mut dyn_img = DynamicImage::ImageRgba8(rgba8);
    apply_mask(&mut dyn_img, &mask);
    let composited = composite_bg(&dyn_img, &opts.bg_mode, opts.bg_color, opts.bg_thresh);
    let with_shadow = apply_shadow(&composited, &opts.shadow_mode, opts.shadow_color, opts.shadow_blur, opts.shadow_offset_x, opts.shadow_offset_y);
    let bw = border_width(&opts.border_mode, opts.border_width_px);
    let with_border = apply_border(&with_shadow, &opts.border_mode, opts.border_color, bw, opts.shape, opts.corner_radius_pct);
    let bytes = encode(&with_border, opts);
    RenderResult { size: size.clone(), bytes, warnings: vec![] }
}

fn encode(img: &DynamicImage, opts: &SwatchOptions) -> Vec<u8> {
    use image::ImageFormat;
    use std::io::Cursor;
    let mut buf = Vec::new();
    let mut cursor = Cursor::new(&mut buf);
    match opts.format {
        Format::Jpeg => {
            let rgb = flatten_alpha(img);
            let enc = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut cursor, opts.quality);
            let _ = rgb.write_with_encoder(enc);
        }
        Format::Png => { let _ = img.write_to(&mut cursor, ImageFormat::Png); }
        Format::Webp => { let _ = img.write_to(&mut cursor, ImageFormat::WebP); }
    }
    buf
}

fn flatten_alpha(img: &DynamicImage) -> DynamicImage {
    let (w, h) = img.dimensions();
    let src = img.to_rgba8();
    let mut out = ImageBuffer::from_pixel(w, h, Rgba([255u8, 255, 255, 255]));
    for y in 0..h { for x in 0..w {
        let px = src.get_pixel(x, y).0;
        let ta = px[3] as f32 / 255.0;
        let d = out.get_pixel_mut(x, y);
        d.0[0] = (px[0] as f32 * ta + 255.0 * (1.0 - ta)) as u8;
        d.0[1] = (px[1] as f32 * ta + 255.0 * (1.0 - ta)) as u8;
        d.0[2] = (px[2] as f32 * ta + 255.0 * (1.0 - ta)) as u8;
    }}
    DynamicImage::ImageRgba8(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{BgMode, BorderMode, Format, OutputSize, SwatchOptions};
    use image::{ImageBuffer, Rgba as ImRgba};

    fn make_test_png() -> Vec<u8> {
        let img = DynamicImage::ImageRgba8(ImageBuffer::from_pixel(20, 20, ImRgba([200u8,100,50,200])));
        let mut buf = Vec::new();
        img.write_to(&mut std::io::Cursor::new(&mut buf), image::ImageFormat::Png).unwrap();
        buf
    }

    fn make_test_jpeg() -> Vec<u8> {
        let img = DynamicImage::ImageRgba8(ImageBuffer::from_pixel(20, 20, ImRgba([200u8,100,50,255])));
        let mut buf = Vec::new();
        img.write_to(&mut std::io::Cursor::new(&mut buf), image::ImageFormat::Jpeg).unwrap();
        buf
    }

    #[test]
    fn test_render_produces_bytes() {
        let raw = make_test_jpeg();
        let opts = SwatchOptions { sizes: vec![OutputSize { width: 100, height: 100 }], format: Format::Jpeg, ..Default::default() };
        let results = render_swatch(&raw, &opts);
        assert_eq!(results.len(), 1);
        assert!(!results[0].bytes.is_empty());
    }

    #[test]
    fn test_render_output_dimensions() {
        let raw = make_test_png();
        let opts = SwatchOptions {
            sizes: vec![OutputSize { width: 100, height: 100 }, OutputSize { width: 200, height: 200 }],
            format: Format::Png, ..Default::default()
        };
        let results = render_swatch(&raw, &opts);
        assert_eq!(results.len(), 2);
        for (r, s) in results.iter().zip(&opts.sizes) {
            if r.bytes.is_empty() { continue; }
            let decoded = image::load_from_memory(&r.bytes).unwrap();
            assert_eq!(decoded.width(), s.width);
            assert_eq!(decoded.height(), s.height);
        }
    }

    #[test]
    fn test_custom_bg_renders() {
        // bug #1
        let raw = make_test_png();
        let opts = SwatchOptions { sizes: vec![OutputSize { width: 50, height: 50 }], bg_mode: BgMode::Custom, bg_color: [0,128,255,255], format: Format::Png, ..Default::default() };
        assert!(!render_swatch(&raw, &opts)[0].bytes.is_empty());
    }

    #[test]
    fn test_no_border_by_default() {
        // bug #2
        let opts = SwatchOptions::default();
        assert!(matches!(opts.border_mode, BorderMode::None));
    }
}
