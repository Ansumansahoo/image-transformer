//! Border rendering. Bug #2 fix: None = no border. Bug #7 fix: inset stroke.

use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use crate::types::{BorderMode, ShapeKind};
use crate::shapes::make_mask;

pub fn border_width(mode: &BorderMode, explicit_px: u32) -> u32 {
    match mode {
        BorderMode::None => 0,
        BorderMode::Thin => 1,
        BorderMode::Medium => 3,
        BorderMode::Thick => 6,
        BorderMode::Custom => explicit_px,
    }
}

pub fn apply_border(img: &DynamicImage, mode: &BorderMode, border_color: [u8; 4], border_width_px: u32, shape: ShapeKind, corner_radius_pct: f32) -> DynamicImage {
    // Bug #2: None must be no-op
    if matches!(mode, BorderMode::None) || border_width_px == 0 { return img.clone(); }
    let (w, h) = img.dimensions();
    let bw = border_width_px;
    let outer_mask = make_mask(w, h, shape, corner_radius_pct);
    let inner_w = (w as i32 - 2 * bw as i32).max(0) as u32;
    let inner_h = (h as i32 - 2 * bw as i32).max(0) as u32;
    let mut result = img.to_rgba8();
    let img_rgba = img.to_rgba8();

    // Build inner mask centred inside outer
    let mut inner_mask: ImageBuffer<Rgba<u8>, Vec<u8>> = ImageBuffer::from_pixel(w, h, Rgba([0u8; 4]));
    if inner_w > 0 && inner_h > 0 {
        let small = make_mask(inner_w, inner_h, shape, corner_radius_pct);
        for y in 0..inner_h { for x in 0..inner_w {
            inner_mask.put_pixel(x + bw, y + bw, *small.get_pixel(x, y));
        }}
    }

    for y in 0..h {
        for x in 0..w {
            let outer_a = outer_mask.get_pixel(x, y).0[3] as u32;
            let inner_a = inner_mask.get_pixel(x, y).0[3] as u32;
            let border_cov = outer_a.saturating_sub(inner_a);
            if border_cov > 0 {
                let ba = (border_color[3] as u32 * border_cov / 255) as u32;
                let orig = img_rgba.get_pixel(x, y).0;
                let ta = ba as f32 / 255.0; let oa = orig[3] as f32 / 255.0;
                let out_a = ta + oa * (1.0 - ta);
                if out_a > 0.0 {
                    result.put_pixel(x, y, Rgba([
                        ((border_color[0] as f32 * ta + orig[0] as f32 * oa * (1.0 - ta)) / out_a) as u8,
                        ((border_color[1] as f32 * ta + orig[1] as f32 * oa * (1.0 - ta)) / out_a) as u8,
                        ((border_color[2] as f32 * ta + orig[2] as f32 * oa * (1.0 - ta)) / out_a) as u8,
                        (out_a * 255.0) as u8,
                    ]));
                }
            }
        }
    }
    DynamicImage::ImageRgba8(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{ImageBuffer, Rgba as ImRgba};

    #[test]
    fn test_no_border_passthrough() {
        let img = DynamicImage::ImageRgba8(ImageBuffer::from_pixel(20, 20, ImRgba([200u8,200,200,255])));
        let r = apply_border(&img, &BorderMode::None, [0,0,0,255], 0, ShapeKind::Square, 0.0);
        assert_eq!(r.to_rgba8().get_pixel(10, 10).0[0], 200);
    }

    #[test]
    fn test_border_width_lookup() {
        assert_eq!(border_width(&BorderMode::None, 5), 0);
        assert_eq!(border_width(&BorderMode::Thin, 0), 1);
        assert_eq!(border_width(&BorderMode::Custom, 7), 7);
    }
}
