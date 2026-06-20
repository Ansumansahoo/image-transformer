//! Bounding-box detection.

use image::{DynamicImage, GenericImageView, Rgba};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BBox {
    pub x: u32,
    pub y: u32,
    pub w: u32,
    pub h: u32,
}

impl BBox {
    pub fn new(x: u32, y: u32, w: u32, h: u32) -> Self {
        BBox { x, y, w, h }
    }

    pub fn expand(&self, pad: u32, img_w: u32, img_h: u32) -> Self {
        let x = self.x.saturating_sub(pad);
        let y = self.y.saturating_sub(pad);
        let x2 = (self.x + self.w + pad).min(img_w);
        let y2 = (self.y + self.h + pad).min(img_h);
        BBox { x, y, w: x2.saturating_sub(x), h: y2.saturating_sub(y) }
    }
}

fn colour_dist(a: Rgba<u8>, b: Rgba<u8>) -> f32 {
    let dr = a.0[0] as f32 - b.0[0] as f32;
    let dg = a.0[1] as f32 - b.0[1] as f32;
    let db = a.0[2] as f32 - b.0[2] as f32;
    (dr * dr + dg * dg + db * db).sqrt()
}

pub fn detect_bbox(img: &DynamicImage, bg_color: Rgba<u8>, threshold: u8) -> BBox {
    const THUMB_MAX: u32 = 256;
    let (orig_w, orig_h) = img.dimensions();
    let thumb = if orig_w > THUMB_MAX || orig_h > THUMB_MAX {
        img.thumbnail(THUMB_MAX, THUMB_MAX)
    } else {
        img.clone()
    };
    let (tw, th) = thumb.dimensions();
    let thumb_rgba = thumb.to_rgba8();
    let thresh_f = threshold as f32;
    let mut min_x = tw;
    let mut min_y = th;
    let mut max_x = 0u32;
    let mut max_y = 0u32;
    let mut found = false;
    for y in 0..th {
        for x in 0..tw {
            let px = thumb_rgba.get_pixel(x, y);
            if px.0[3] < 10 { continue; }
            if colour_dist(*px, bg_color) < thresh_f { continue; }
            if x < min_x { min_x = x; }
            if y < min_y { min_y = y; }
            if x > max_x { max_x = x; }
            if y > max_y { max_y = y; }
            found = true;
        }
    }
    if !found { return BBox::new(0, 0, orig_w, orig_h); }
    let scale_x = orig_w as f32 / tw as f32;
    let scale_y = orig_h as f32 / th as f32;
    let x = (min_x as f32 * scale_x) as u32;
    let y = (min_y as f32 * scale_y) as u32;
    let x2 = ((max_x + 1) as f32 * scale_x).ceil() as u32;
    let y2 = ((max_y + 1) as f32 * scale_y).ceil() as u32;
    BBox::new(x, y, x2.min(orig_w).saturating_sub(x), y2.min(orig_h).saturating_sub(y))
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{ImageBuffer, Rgba as ImRgba};

    #[test]
    fn test_bbox_all_background() {
        let img = ImageBuffer::from_pixel(8, 8, ImRgba([255u8, 255, 255, 255]));
        let dyn_img = DynamicImage::ImageRgba8(img);
        let bbox = detect_bbox(&dyn_img, ImRgba([255, 255, 255, 255]), 30);
        assert_eq!(bbox, BBox::new(0, 0, 8, 8));
    }
}
