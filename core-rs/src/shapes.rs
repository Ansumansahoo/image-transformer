//! Shape masks — all 7 shapes with anti-aliasing.

use image::{DynamicImage, ImageBuffer, Rgba};
use std::f32::consts::PI;
use crate::types::ShapeKind;

pub fn make_mask(w: u32, h: u32, shape: ShapeKind, corner_radius_pct: f32) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let mut mask = ImageBuffer::new(w, h);
    let cx = w as f32 / 2.0;
    let cy = h as f32 / 2.0;
    match shape {
        ShapeKind::Square  => fill_rect(&mut mask, w, h),
        ShapeKind::Rounded => fill_rounded_rect(&mut mask, w, h, corner_radius_pct, cx, cy),
        ShapeKind::Circle  => fill_ellipse(&mut mask, w, h, cx, cy, cx - 0.5, cy - 0.5),
        ShapeKind::Diamond => fill_polygon(&mut mask, w, h, &diamond_points(cx, cy, cx, cy)),
        ShapeKind::Hexagon => fill_polygon(&mut mask, w, h, &ngon_points(cx, cy, cx.min(cy) - 0.5, 6, -PI / 2.0)),
        ShapeKind::Pentagon=> fill_polygon(&mut mask, w, h, &ngon_points(cx, cy, cx.min(cy) - 0.5, 5, -PI / 2.0)),
        ShapeKind::Octagon => fill_polygon(&mut mask, w, h, &ngon_points(cx, cy, cx.min(cy) - 0.5, 8, -PI / 8.0)),
    }
    mask
}

pub fn apply_mask(img: &mut DynamicImage, mask: &ImageBuffer<Rgba<u8>, Vec<u8>>) {
    let (w, h) = (img.width(), img.height());
    let rgba = img.as_mut_rgba8().expect("image must be RGBA8");
    for y in 0..h {
        for x in 0..w {
            let mask_px = mask.get_pixel(x, y);
            let img_px = rgba.get_pixel_mut(x, y);
            let ma = mask_px.0[3] as u32;
            img_px.0[3] = ((img_px.0[3] as u32 * ma + 127) / 255) as u8;
        }
    }
}

fn set_alpha(mask: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, x: u32, y: u32, alpha: u8) {
    mask.put_pixel(x, y, Rgba([255, 255, 255, alpha]));
}

fn fill_rect(mask: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, w: u32, h: u32) {
    for y in 0..h { for x in 0..w { set_alpha(mask, x, y, 255); } }
}

fn fill_ellipse(mask: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, w: u32, h: u32, cx: f32, cy: f32, rx: f32, ry: f32) {
    for y in 0..h {
        for x in 0..w {
            let dx = (x as f32 + 0.5 - cx) / rx;
            let dy = (y as f32 + 0.5 - cy) / ry;
            let d2 = dx * dx + dy * dy;
            let a = if d2 <= 0.81 { 255 } else if d2 >= 1.0 { 0 } else { ((1.0 - (d2.sqrt() - 0.9) / 0.1) * 255.0) as u8 };
            set_alpha(mask, x, y, a);
        }
    }
}

fn fill_rounded_rect(mask: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, w: u32, h: u32, corner_pct: f32, cx: f32, cy: f32) {
    let r = (cx.min(cy) * (corner_pct / 100.0).clamp(0.0, 0.5)).max(1.0);
    for y in 0..h {
        for x in 0..w {
            let px = x as f32 + 0.5;
            let py = y as f32 + 0.5;
            let a = if px >= r && px <= w as f32 - r { 255 }
                else if py >= r && py <= h as f32 - r { 255 }
                else {
                    let ccx = if px < cx { r } else { w as f32 - r };
                    let ccy = if py < cy { r } else { h as f32 - r };
                    let d = ((px - ccx).powi(2) + (py - ccy).powi(2)).sqrt();
                    if d <= r - 0.5 { 255 } else if d >= r + 0.5 { 0 } else { ((1.0 - (d - (r - 0.5))) * 255.0) as u8 }
                };
            set_alpha(mask, x, y, a);
        }
    }
}

fn diamond_points(cx: f32, cy: f32, rx: f32, ry: f32) -> Vec<(f32, f32)> {
    vec![(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
}

fn ngon_points(cx: f32, cy: f32, r: f32, n: u32, start: f32) -> Vec<(f32, f32)> {
    (0..n).map(|i| { let a = start + 2.0 * PI * i as f32 / n as f32; (cx + r * a.cos(), cy + r * a.sin()) }).collect()
}

fn fill_polygon(mask: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, w: u32, h: u32, pts: &[(f32, f32)]) {
    for y in 0..h {
        for x in 0..w {
            let samples = [(x as f32 + 0.25, y as f32 + 0.25),(x as f32 + 0.75, y as f32 + 0.25),(x as f32 + 0.25, y as f32 + 0.75),(x as f32 + 0.75, y as f32 + 0.75)];
            let inside = samples.iter().filter(|&&(px, py)| pip(px, py, pts)).count();
            set_alpha(mask, x, y, (inside * 64) as u8);
        }
    }
}

fn pip(px: f32, py: f32, pts: &[(f32, f32)]) -> bool {
    let n = pts.len(); let mut inside = false; let mut j = n - 1;
    for i in 0..n {
        let (xi, yi) = pts[i]; let (xj, yj) = pts[j];
        if ((yi > py) != (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi) { inside = !inside; }
        j = i;
    }
    inside
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_square_all_opaque() {
        let mask = make_mask(10, 10, ShapeKind::Square, 0.0);
        assert_eq!(mask.get_pixel(5, 5).0[3], 255);
    }

    #[test]
    fn test_circle_corners_transparent() {
        let mask = make_mask(100, 100, ShapeKind::Circle, 0.0);
        assert_eq!(mask.get_pixel(0, 0).0[3], 0);
    }
}
