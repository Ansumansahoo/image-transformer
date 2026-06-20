//! Crop/resize pipeline + EXIF orientation (bug #5 fix).

use image::{DynamicImage, GenericImageView, imageops::FilterType};
use crate::bbox::BBox;
use crate::types::{CropEngine, OutputSize};

pub fn auto_orient(img: DynamicImage, raw_bytes: &[u8]) -> DynamicImage {
    let orientation = read_exif_orientation(raw_bytes).unwrap_or(1);
    apply_exif_orientation(img, orientation)
}

fn read_exif_orientation(raw: &[u8]) -> Option<u32> {
    use std::io::Cursor;
    let exif = exif::Reader::new()
        .read_from_container(&mut Cursor::new(raw))
        .ok()?;
    let field = exif.get_field(exif::Tag::Orientation, exif::In::PRIMARY)?;
    field.value.get_uint(0)
}

fn apply_exif_orientation(img: DynamicImage, orientation: u32) -> DynamicImage {
    match orientation {
        1 => img,
        2 => DynamicImage::ImageRgba8(image::imageops::flip_horizontal(&img.to_rgba8())),
        3 => DynamicImage::ImageRgba8(image::imageops::rotate180(&img.to_rgba8())),
        4 => DynamicImage::ImageRgba8(image::imageops::flip_vertical(&img.to_rgba8())),
        5 => { let r = image::imageops::rotate90(&img.to_rgba8()); DynamicImage::ImageRgba8(image::imageops::flip_horizontal(&r)) }
        6 => DynamicImage::ImageRgba8(image::imageops::rotate90(&img.to_rgba8())),
        7 => { let r = image::imageops::rotate270(&img.to_rgba8()); DynamicImage::ImageRgba8(image::imageops::flip_horizontal(&r)) }
        8 => DynamicImage::ImageRgba8(image::imageops::rotate270(&img.to_rgba8())),
        _ => img,
    }
}

pub fn crop_and_resize(src: &DynamicImage, size: &OutputSize, engine: CropEngine, bbox: &BBox) -> DynamicImage {
    match engine {
        CropEngine::Smart  => smart_crop(src, size, bbox),
        CropEngine::Center => center_crop(src, size),
        CropEngine::Contain=> contain(src, size),
        CropEngine::Cover  => cover(src, size),
        CropEngine::Stretch=> stretch(src, size),
    }
}

fn smart_crop(src: &DynamicImage, size: &OutputSize, bbox: &BBox) -> DynamicImage {
    let (img_w, img_h) = src.dimensions();
    if bbox.w == 0 || bbox.h == 0 {
        return src.resize_exact(size.width, size.height, FilterType::Lanczos3);
    }
    let padding = ((bbox.w.min(bbox.h)) as f32 * 0.04) as u32 + 2;
    let expanded = bbox.expand(padding, img_w, img_h);
    let side = expanded.w.max(expanded.h);
    let cx = expanded.x + expanded.w / 2;
    let cy = expanded.y + expanded.h / 2;
    let sq_x = cx.saturating_sub(side / 2).min(img_w.saturating_sub(side));
    let sq_y = cy.saturating_sub(side / 2).min(img_h.saturating_sub(side));
    let sq_side = side.min(img_w - sq_x).min(img_h - sq_y);
    let cropped = src.crop_imm(sq_x, sq_y, sq_side, sq_side);
    cropped.resize_exact(size.width, size.height, FilterType::Lanczos3)
}

fn center_crop(src: &DynamicImage, size: &OutputSize) -> DynamicImage {
    let (w, h) = src.dimensions();
    let side = w.min(h);
    let x = (w - side) / 2;
    let y = (h - side) / 2;
    src.crop_imm(x, y, side, side).resize_exact(size.width, size.height, FilterType::Lanczos3)
}

fn contain(src: &DynamicImage, size: &OutputSize) -> DynamicImage {
    let (w, h) = src.dimensions();
    let scale = (size.width as f32 / w as f32).min(size.height as f32 / h as f32);
    let nw = (w as f32 * scale).round() as u32;
    let nh = (h as f32 * scale).round() as u32;
    let resized = src.resize(nw, nh, FilterType::Lanczos3);
    let mut canvas = DynamicImage::new_rgba8(size.width, size.height);
    let ox = (size.width.saturating_sub(nw)) / 2;
    let oy = (size.height.saturating_sub(nh)) / 2;
    image::imageops::overlay(&mut canvas, &resized, ox as i64, oy as i64);
    canvas
}

fn cover(src: &DynamicImage, size: &OutputSize) -> DynamicImage {
    let (w, h) = src.dimensions();
    let scale = (size.width as f32 / w as f32).max(size.height as f32 / h as f32);
    let nw = (w as f32 * scale).round() as u32;
    let nh = (h as f32 * scale).round() as u32;
    let resized = src.resize_exact(nw, nh, FilterType::Lanczos3);
    let cx = (nw.saturating_sub(size.width)) / 2;
    let cy = (nh.saturating_sub(size.height)) / 2;
    resized.crop_imm(cx, cy, size.width, size.height)
}

fn stretch(src: &DynamicImage, size: &OutputSize) -> DynamicImage {
    src.resize_exact(size.width, size.height, FilterType::Lanczos3)
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{DynamicImage, ImageBuffer, Rgba};

    fn make_img(w: u32, h: u32) -> DynamicImage {
        DynamicImage::ImageRgba8(ImageBuffer::from_pixel(w, h, Rgba([100u8, 150, 200, 255])))
    }

    #[test]
    fn test_contain_output_size() {
        let img = make_img(800, 400);
        let size = OutputSize { width: 300, height: 300 };
        let bbox = BBox::new(0, 0, 800, 400);
        let out = crop_and_resize(&img, &size, CropEngine::Contain, &bbox);
        assert_eq!(out.dimensions(), (300, 300));
    }

    #[test]
    fn test_exif_rotate90_swaps_dims() {
        let img = make_img(4, 8);
        let rotated = apply_exif_orientation(img, 6);
        assert_eq!(rotated.dimensions(), (8, 4));
    }
}
