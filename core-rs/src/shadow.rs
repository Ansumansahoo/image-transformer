//! Drop shadow compositing.

use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use crate::bg::alpha_over;
use crate::types::ShadowMode;

pub fn apply_shadow(img: &DynamicImage, mode: &ShadowMode, shadow_color: [u8; 4], shadow_blur: f32, offset_x: i32, offset_y: i32) -> DynamicImage {
    if matches!(mode, ShadowMode::None) { return img.clone(); }
    let (w, h) = img.dimensions();
    let (blur, ox, oy) = match mode {
        ShadowMode::None => unreachable!(),
        ShadowMode::Soft => (shadow_blur.max(2.0), offset_x, offset_y),
        ShadowMode::Hard => (0.5, offset_x, offset_y),
        ShadowMode::Glow => (shadow_blur * 2.0, 0, 0),
    };
    let img_rgba = img.to_rgba8();
    let mut shadow_layer: ImageBuffer<Rgba<u8>, Vec<u8>> = ImageBuffer::new(w, h);
    for y in 0..h {
        for x in 0..w {
            let a = img_rgba.get_pixel(x, y).0[3];
            shadow_layer.put_pixel(x, y, Rgba([shadow_color[0], shadow_color[1], shadow_color[2], ((a as u32 * shadow_color[3] as u32) / 255) as u8]));
        }
    }
    let blurred = if blur > 0.5 { DynamicImage::ImageRgba8(shadow_layer).blur(blur) } else { DynamicImage::ImageRgba8(shadow_layer) };
    let mut result: ImageBuffer<Rgba<u8>, Vec<u8>> = ImageBuffer::new(w, h);
    let blurred_rgba = blurred.to_rgba8();
    for y in 0..h {
        for x in 0..w {
            let sx = x as i32 - ox; let sy = y as i32 - oy;
            if sx >= 0 && sy >= 0 && sx < w as i32 && sy < h as i32 {
                result.put_pixel(x, y, *blurred_rgba.get_pixel(sx as u32, sy as u32));
            }
        }
    }
    alpha_over(DynamicImage::ImageRgba8(result), img)
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{ImageBuffer, Rgba as ImRgba};

    #[test]
    fn test_no_shadow_passthrough() {
        let img = DynamicImage::ImageRgba8(ImageBuffer::from_pixel(10, 10, ImRgba([100u8,100,100,255])));
        let r = apply_shadow(&img, &ShadowMode::None, [0,0,0,180], 4.0, 2, 2);
        assert_eq!(r.to_rgba8().get_pixel(5, 5).0[0], 100);
    }

    #[test]
    fn test_soft_shadow_same_size() {
        let img = DynamicImage::ImageRgba8(ImageBuffer::from_pixel(50, 50, ImRgba([200u8,200,200,255])));
        let r = apply_shadow(&img, &ShadowMode::Soft, [0,0,0,180], 4.0, 3, 3);
        assert_eq!(r.dimensions(), (50, 50));
    }
}
