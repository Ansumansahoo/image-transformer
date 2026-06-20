//! Color utilities: hex parsing, dominant color detection.

use image::{DynamicImage, GenericImageView, Rgba};

pub fn parse_hex_color(s: &str) -> Result<[u8; 4], String> {
    let s = s.trim().trim_start_matches('#');
    match s.len() {
        3 => {
            let r = u8::from_str_radix(&s[0..1].repeat(2), 16).map_err(|e| e.to_string())?;
            let g = u8::from_str_radix(&s[1..2].repeat(2), 16).map_err(|e| e.to_string())?;
            let b = u8::from_str_radix(&s[2..3].repeat(2), 16).map_err(|e| e.to_string())?;
            Ok([r, g, b, 255])
        }
        6 => {
            let r = u8::from_str_radix(&s[0..2], 16).map_err(|e| e.to_string())?;
            let g = u8::from_str_radix(&s[2..4], 16).map_err(|e| e.to_string())?;
            let b = u8::from_str_radix(&s[4..6], 16).map_err(|e| e.to_string())?;
            Ok([r, g, b, 255])
        }
        8 => {
            let r = u8::from_str_radix(&s[0..2], 16).map_err(|e| e.to_string())?;
            let g = u8::from_str_radix(&s[2..4], 16).map_err(|e| e.to_string())?;
            let b = u8::from_str_radix(&s[4..6], 16).map_err(|e| e.to_string())?;
            let a = u8::from_str_radix(&s[6..8], 16).map_err(|e| e.to_string())?;
            Ok([r, g, b, a])
        }
        _ => Err(format!("invalid hex color: #{}", s)),
    }
}

pub fn to_hex_color(rgba: [u8; 4]) -> String {
    format!("#{:02x}{:02x}{:02x}", rgba[0], rgba[1], rgba[2])
}

pub fn dominant_color(img: &DynamicImage, bg_color: Rgba<u8>, bg_thresh: u8) -> [u8; 4] {
    const THUMB_MAX: u32 = 64;
    let thumb = img.thumbnail(THUMB_MAX, THUMB_MAX);
    let rgba = thumb.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut r_sum = vec![0u64; 4096];
    let mut g_sum = vec![0u64; 4096];
    let mut b_sum = vec![0u64; 4096];
    let mut counts = vec![0u32; 4096];
    let thresh = bg_thresh as f32;
    for y in 0..h {
        for x in 0..w {
            let px = rgba.get_pixel(x, y);
            if px.0[3] < 10 { continue; }
            let dr = px.0[0] as f32 - bg_color.0[0] as f32;
            let dg = px.0[1] as f32 - bg_color.0[1] as f32;
            let db = px.0[2] as f32 - bg_color.0[2] as f32;
            if (dr*dr + dg*dg + db*db).sqrt() < thresh { continue; }
            let ri = (px.0[0] >> 4) as usize;
            let gi = (px.0[1] >> 4) as usize;
            let bi = (px.0[2] >> 4) as usize;
            let idx = ri * 256 + gi * 16 + bi;
            counts[idx] += 1;
            r_sum[idx] += px.0[0] as u64;
            g_sum[idx] += px.0[1] as u64;
            b_sum[idx] += px.0[2] as u64;
        }
    }
    let (best_idx, best_count) = counts.iter().enumerate().max_by_key(|(_, &c)| c).unwrap_or((0, &0));
    if *best_count == 0 { return [255, 255, 255, 255]; }
    let n = counts[best_idx] as u64;
    [(r_sum[best_idx] / n) as u8, (g_sum[best_idx] / n) as u8, (b_sum[best_idx] / n) as u8, 255]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_hex() {
        assert_eq!(parse_hex_color("#ff0000").unwrap(), [255, 0, 0, 255]);
        assert_eq!(parse_hex_color("#f00").unwrap(), [255, 0, 0, 255]);
    }

    #[test]
    fn test_to_hex() {
        assert_eq!(to_hex_color([255, 128, 0, 255]), "#ff8000");
    }
}
