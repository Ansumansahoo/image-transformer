//! Background compositing. Bug #1 fix: BgMode::Custom paints chosen color.

use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use crate::color::dominant_color;
use crate::types::BgMode;

pub fn composite_bg(fg: &DynamicImage, bg_mode: &BgMode, bg_color: [u8; 4], bg_thresh: u8) -> DynamicImage {
    let (w, h) = fg.dimensions();
    match bg_mode {
        BgMode::Transparent => fg.clone(),
        BgMode::White => alpha_over(solid_color(w, h, dominant_color(fg, Rgba([255,255,255,255]), bg_thresh)), fg),
        BgMode::Custom => alpha_over(solid_color(w, h, bg_color), fg), // bug #1 fix
        BgMode::Original => alpha_over(solid_color(w, h, [255,255,255,255]), fg),
        BgMode::Blur => alpha_over(fg.blur(10.0), fg),
    }
}

fn solid_color(w: u32, h: u32, rgba: [u8; 4]) -> DynamicImage {
    DynamicImage::ImageRgba8(ImageBuffer::from_pixel(w, h, Rgba(rgba)))
}

pub fn alpha_over(mut bottom: DynamicImage, top: &DynamicImage) -> DynamicImage {
    let (w, h) = bottom.dimensions();
    let bot = bottom.as_mut_rgba8().unwrap();
    let top_rgba = top.to_rgba8();
    for y in 0..h {
        for x in 0..w {
            let t = top_rgba.get_pixel(x, y).0;
            let b = bot.get_pixel_mut(x, y);
            let ta = t[3] as f32 / 255.0;
            let ba = b.0[3] as f32 / 255.0;
            let out_a = ta + ba * (1.0 - ta);
            if out_a > 0.0 {
                b.0[0] = ((t[0] as f32 * ta + b.0[0] as f32 * ba * (1.0 - ta)) / out_a) as u8;
                b.0[1] = ((t[1] as f32 * ta + b.0[1] as f32 * ba * (1.0 - ta)) / out_a) as u8;
                b.0[2] = ((t[2] as f32 * ta + b.0[2] as f32 * ba * (1.0 - ta)) / out_a) as u8;
                b.0[3] = (out_a * 255.0) as u8;
            }
        }
    }
    bottom
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{ImageBuffer, Rgba as ImRgba};

    fn make(r: u8, g: u8, b: u8, a: u8) -> DynamicImage {
        DynamicImage::ImageRgba8(ImageBuffer::from_pixel(10, 10, ImRgba([r, g, b, a])))
    }

    #[test]
    fn test_custom_bg_paints_color() {
        // bug #1 fix
        let fg = make(0, 0, 0, 0);
        let result = composite_bg(&fg, &BgMode::Custom, [255, 0, 0, 255], 30);
        assert_eq!(result.to_rgba8().get_pixel(5, 5).0[0], 255);
    }

    #[test]
    fn test_transparent_passthrough() {
        let fg = make(100, 100, 100, 128);
        let result = composite_bg(&fg, &BgMode::Transparent, [255,255,255,255], 30);
        assert_eq!(result.to_rgba8().get_pixel(5, 5).0[3], 128);
    }
}
