//! Mandelbrot with real threads in Rust - counterpart to mandelbrot.py and csharp/MandelBench.
//! Same tile layout, same formula (smoothed iteration count, escape radius 16), same color palette,
//! same protocol as the C# program:
//!
//! Input (stdin, JSON): width, height, maxIter, tile, cx, cy, cw, rot90, threads, order[], affinity[], emitTiles, simd
//! Output (stdout):
//!   READY                    after warm-up; the measurement starts afterwards
//!   B i worker cpu ms len    per finished tile, followed directly by len bytes of RGB
//!   R {json}                 result: seconds, cpu_time, inside, sum_nu, threads_seen, simd

use std::io::{Read, Write};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::time::Instant;

#[derive(Clone)]
struct Config {
    width: usize,
    height: usize,
    max_iter: u32,
    tile: usize,
    cx: f64,
    cy: f64,
    cw: f64,
    rot90: bool,
    threads: usize,
    order: Vec<usize>,
    affinity: Vec<usize>,
    emit_tiles: bool,
    simd: bool,
    cardioid: bool,
}

/// Main cardioid or the period-2 bulb to its left: certainly inside the set (same formula as mandelbrot.py)
#[inline]
fn in_main_bulbs(x: f64, y: f64) -> bool {
    let xm = x - 0.25;
    let y2 = y * y;
    let q = xm * xm + y2;
    q * (q + xm) <= 0.25 * y2 || (x + 1.0) * (x + 1.0) + y2 <= 0.0625
}

struct Tile {
    index: usize,
    x: usize,
    y: usize,
    w: usize,
    h: usize,
}

// ---- Windows functions (kernel32) for affinity, priority and core number ----
#[cfg(windows)]
mod native {
    extern "system" {
        fn GetCurrentThread() -> isize;
        fn SetThreadAffinityMask(thread: isize, mask: usize) -> usize;
        fn GetCurrentProcessorNumber() -> u32;
        fn GetCurrentProcess() -> isize;
        fn SetPriorityClass(process: isize, class: u32) -> i32;
    }
    pub fn pin(lp: usize) {
        unsafe { SetThreadAffinityMask(GetCurrentThread(), 1usize << lp) };
    }
    pub fn cpu() -> u32 {
        unsafe { GetCurrentProcessorNumber() }
    }
    pub fn below_normal() {
        unsafe { SetPriorityClass(GetCurrentProcess(), 0x4000) };  // like the Python workers and C#
    }
}
// Linux: functions of the C library (glibc), declared here directly - no external crates needed
#[cfg(target_os = "linux")]
mod native {
    extern "C" {
        fn sched_setaffinity(pid: i32, size: usize, mask: *const u64) -> i32;
        fn sched_getcpu() -> i32;
        fn setpriority(which: i32, who: u32, prio: i32) -> i32;
    }
    pub fn pin(lp: usize) {
        if lp < 1024 {
            let mut mask = [0u64; 16]; // cpu_set_t: 1024 bits
            mask[lp / 64] = 1u64 << (lp % 64);
            unsafe { sched_setaffinity(0, std::mem::size_of_val(&mask), mask.as_ptr()) }; // 0 = this thread
        }
    }
    pub fn cpu() -> u32 {
        let c = unsafe { sched_getcpu() };
        if c < 0 { 0 } else { c as u32 }
    }
    pub fn below_normal() {
        // nice 5 (PRIO_PROCESS = 0, 0 = this process); called before the worker threads start, which inherit it
        unsafe { setpriority(0, 0, 5) };
    }
}
#[cfg(not(any(windows, target_os = "linux")))]
mod native {
    pub fn pin(_: usize) {}
    pub fn cpu() -> u32 { 0 }
    pub fn below_normal() {}
}

// ---- tiny JSON reader for the flat configuration (no external crates) ----
fn raw<'a>(json: &'a str, key: &str) -> Option<&'a str> {
    let start = json.find(&format!("\"{key}\""))? + key.len() + 2;
    let rest = json[start..].trim_start().strip_prefix(':')?.trim_start();
    let end = if rest.starts_with('[') {
        rest.find(']')? + 1
    } else {
        rest.find(|c| c == ',' || c == '}').unwrap_or(rest.len())
    };
    Some(rest[..end].trim())
}
fn num(json: &str, key: &str) -> f64 {
    raw(json, key).and_then(|v| v.parse().ok()).unwrap_or_else(|| panic!("Field {key} missing"))
}
fn flag(json: &str, key: &str) -> bool {
    raw(json, key) == Some("true")
}
fn list(json: &str, key: &str) -> Vec<usize> {
    match raw(json, key) {
        Some(v) if v.starts_with('[') => v
            .trim_matches(|c| c == '[' || c == ']')
            .split(',')
            .filter_map(|s| s.trim().parse().ok())
            .collect(),
        _ => Vec::new(),
    }
}

fn read_config() -> Config {
    let mut s = String::new();
    std::io::stdin().read_to_string(&mut s).expect("stdin");
    Config {
        width: num(&s, "width") as usize,
        height: num(&s, "height") as usize,
        max_iter: num(&s, "maxIter") as u32,
        tile: num(&s, "tile") as usize,
        cx: num(&s, "cx"),
        cy: num(&s, "cy"),
        cw: num(&s, "cw"),
        rot90: flag(&s, "rot90"),
        threads: num(&s, "threads") as usize,
        order: list(&s, "order"),
        affinity: list(&s, "affinity"),
        emit_tiles: flag(&s, "emitTiles"),
        simd: flag(&s, "simd"),
        cardioid: flag(&s, "cardioid"),
    }
}

// ---- color palette like _palette() in mandelbrot.py ----
fn build_palette(n: usize) -> Vec<u8> {
    let stops = [0.0, 0.16, 0.42, 0.6425, 0.8575, 1.0];
    let cols = [[0.0, 7.0, 100.0], [32.0, 107.0, 203.0], [237.0, 255.0, 255.0],
                [255.0, 170.0, 0.0], [0.0, 2.0, 0.0], [0.0, 7.0, 100.0]];
    let mut pal = vec![0u8; n * 3];
    for i in 0..n {
        let tt = i as f64 / n as f64;
        let mut j = 0;
        while j < stops.len() - 2 && tt > stops[j + 1] {
            j += 1;
        }
        for k in 0..3 {
            let slope = (cols[j + 1][k] - cols[j][k]) / (stops[j + 1] - stops[j]);
            pal[i * 3 + k] = (slope * (tt - stops[j]) + cols[j][k]) as u8;
        }
    }
    pal
}

#[inline]
fn store(rgb: &mut [u8], p: usize, nu: f64, pal: &[u8], inside: &mut u64, sum: &mut f64) {
    if nu < 0.0 {
        *inside += 1;
        rgb[p] = 0; rgb[p + 1] = 0; rgb[p + 2] = 0;
        return;
    }
    *sum += nu;
    let idx = (((nu.sqrt() * 64.0) as i64) % (pal.len() as i64 / 3)) as usize * 3;
    rgb[p..p + 3].copy_from_slice(&pal[idx..idx + 3]);
}

#[inline]
fn coords(c: &Config, px: usize, py: usize) -> (f64, f64) {
    let scale = c.cw / c.width as f64;
    let sx = ((px as f64 - c.width as f64 / 2.0) + 0.5) * scale;
    let sy = ((py as f64 - c.height as f64 / 2.0) + 0.5) * scale;
    if c.rot90 { (c.cx + sy, c.cy + sx) } else { (c.cx + sx, c.cy - sy) }  // rotated: right = +Im, down = +Re
}

/// Pixel by pixel, like _escape_numba + _colorize
fn render_scalar(t: &Tile, c: &Config, pal: &[u8], rgb: &mut [u8]) -> (u64, f64) {
    let (mut inside, mut sum) = (0u64, 0.0f64);
    for y in 0..t.h {
        for x in 0..t.w {
            let (cr, ci) = coords(c, t.x + x, t.y + y);
            let (mut zr, mut zi, mut nu) = (0.0f64, 0.0f64, -1.0f64);
            let max_iter = if c.cardioid && in_main_bulbs(cr, ci) { 0 } else { c.max_iter };  // inside the set
            for it in 0..max_iter {
                let zr2 = zr * zr;
                let zi2 = zi * zi;
                if zr2 + zi2 > 256.0 {
                    nu = (it + 1) as f64 - (0.5 * (zr2 + zi2).ln()).log2();
                    break;
                }
                zi = 2.0 * zr * zi + ci;
                zr = zr2 - zi2 + cr;
            }
            store(rgb, (y * t.w + x) * 3, nu, pal, &mut inside, &mut sum);
        }
    }
    (inside, sum)
}

/// 4 pixels at once with AVX2. Same operations in the same order, no FMA -> same image.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn render_simd(t: &Tile, c: &Config, pal: &[u8], rgb: &mut [u8]) -> (u64, f64) {
    use std::arch::x86_64::*;
    let (mut inside, mut sum) = (0u64, 0.0f64);
    let limit = _mm256_set1_pd(256.0);
    let two = _mm256_set1_pd(2.0);
    for y in 0..t.h {
        let mut x = 0;
        while x + 4 <= t.w {
            let (mut lr, mut li) = ([0.0f64; 4], [0.0f64; 4]);
            for l in 0..4 {
                let (a, b) = coords(c, t.x + x + l, t.y + y);
                lr[l] = a;
                li[l] = b;
            }
            let cr = _mm256_loadu_pd(lr.as_ptr());
            let ci = _mm256_loadu_pd(li.as_ptr());
            let (mut zr, mut zi) = (_mm256_setzero_pd(), _mm256_setzero_pd());
            let mut esc_it = [-1i64; 4];
            let mut esc_r2 = [0.0f64; 4];
            let mut active = 0b1111u32;
            if c.cardioid {  // lanes in the cardioid/bulb count as finished from the start
                for l in 0..4 {
                    if in_main_bulbs(lr[l], li[l]) {
                        active &= !(1 << l);
                    }
                }
            }
            for it in 0..if active == 0 { 0 } else { c.max_iter } {
                let zr2 = _mm256_mul_pd(zr, zr);
                let zi2 = _mm256_mul_pd(zi, zi);
                let r2 = _mm256_add_pd(zr2, zi2);
                let done = (_mm256_movemask_pd(_mm256_cmp_pd::<_CMP_GT_OQ>(r2, limit)) as u32) & active;
                if done != 0 {
                    let mut tmp = [0.0f64; 4];
                    _mm256_storeu_pd(tmp.as_mut_ptr(), r2);
                    for l in 0..4 {
                        if done >> l & 1 == 1 {
                            esc_it[l] = it as i64;
                            esc_r2[l] = tmp[l];
                        }
                    }
                    active &= !done;
                    if active == 0 {
                        break;
                    }
                }
                zi = _mm256_add_pd(_mm256_mul_pd(_mm256_mul_pd(two, zr), zi), ci);
                zr = _mm256_add_pd(_mm256_sub_pd(zr2, zi2), cr);
            }
            for l in 0..4 {
                let nu = if esc_it[l] < 0 { -1.0 } else { (esc_it[l] + 1) as f64 - (0.5 * esc_r2[l].ln()).log2() };
                store(rgb, (y * t.w + x + l) * 3, nu, pal, &mut inside, &mut sum);
            }
            x += 4;
        }
        while x < t.w {  // remainder of a row: scalar
            let one = Tile { index: 0, x: t.x + x, y: t.y + y, w: 1, h: 1 };
            let mut px = [0u8; 3];
            let (i, s) = render_scalar(&one, c, pal, &mut px);
            inside += i;
            sum += s;
            rgb[(y * t.w + x) * 3..(y * t.w + x) * 3 + 3].copy_from_slice(&px);
            x += 1;
        }
    }
    (inside, sum)
}

fn main() {
    let cfg = read_config();
    native::below_normal();
    let pal = build_palette(1024);

    #[cfg(target_arch = "x86_64")]
    let simd = cfg.simd && is_x86_feature_detected!("avx2");
    #[cfg(not(target_arch = "x86_64"))]
    let simd = false;
    let render = |t: &Tile, rgb: &mut [u8]| -> (u64, f64) {
        #[cfg(target_arch = "x86_64")]
        if simd {
            return unsafe { render_simd(t, &cfg, &pal, rgb) };
        }
        render_scalar(t, &cfg, &pal, rgb)
    };

    let mut tiles = Vec::new();
    for y in (0..cfg.height).step_by(cfg.tile) {
        for x in (0..cfg.width).step_by(cfg.tile) {
            tiles.push(Tile { index: tiles.len(), x, y, w: cfg.tile.min(cfg.width - x), h: cfg.tile.min(cfg.height - y) });
        }
    }
    let order: Vec<usize> = if cfg.order.is_empty() { (0..tiles.len()).collect() } else { cfg.order.clone() };

    let out = Mutex::new(std::io::stdout());
    {
        let mut o = out.lock().unwrap();
        writeln!(o, "{}", if simd { "READY simd" } else { "READY" }).unwrap();
        o.flush().unwrap();
    }

    let next = AtomicUsize::new(0);
    let totals = Mutex::new((0u64, 0.0f64, 0.0f64, 0usize));  // inside, sum_nu, cpu_time, threads_seen
    let start = Instant::now();
    std::thread::scope(|s| {
        for index in 0..cfg.threads {
            let (next, totals, out, order, tiles, render, cfg) = (&next, &totals, &out, &order, &tiles, &render, &cfg);
            s.spawn(move || {
                if !cfg.affinity.is_empty() {
                    native::pin(cfg.affinity[index % cfg.affinity.len()]);
                }
                let (mut inside, mut sum, mut cpu) = (0u64, 0.0f64, 0.0f64);
                loop {
                    let k = next.fetch_add(1, Ordering::Relaxed);
                    if k >= order.len() {
                        break;
                    }
                    let t = &tiles[order[k]];
                    let t0 = Instant::now();
                    let mut rgb = vec![0u8; t.w * t.h * 3];
                    let (i, su) = render(t, &mut rgb);
                    let sec = t0.elapsed().as_secs_f64();
                    inside += i;
                    sum += su;
                    cpu += sec;
                    if cfg.emit_tiles {
                        let mut o = out.lock().unwrap();
                        write!(o, "B {} {} {} {:.1} {}\n", t.index, index, native::cpu(), sec * 1000.0, rgb.len()).unwrap();
                        o.write_all(&rgb).unwrap();
                        o.flush().unwrap();
                    }
                }
                let mut tot = totals.lock().unwrap();
                tot.0 += inside;
                tot.1 += sum;
                tot.2 += cpu;
                tot.3 += 1;
            });
        }
    });
    let seconds = start.elapsed().as_secs_f64();
    let (inside, sum, cpu, seen) = *totals.lock().unwrap();
    let mut o = out.lock().unwrap();
    writeln!(o, "R {{\"seconds\":{seconds},\"cpu_time\":{cpu},\"inside\":{inside},\"sum_nu\":{sum},\"threads_seen\":{seen},\"simd\":{simd}}}").unwrap();
    o.flush().unwrap();
}
