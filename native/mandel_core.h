/* Shared compute core for the C, C++ and assembler variants.
 * Same tile layout, same formula (smoothed iteration count, escape radius 16) and same color palette
 * as mandelbrot.py, C# and Rust; same protocol (see csharp/MandelBench/Program.cs).
 *
 * Compiled with /O2 /fp:precise (without /arch:AVX2, see build.bat; AVX2 is checked at runtime):
 * no contracted multiply/add operations (FMA), so that every pixel matches the other languages bit for bit.
 */
#pragma once
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <immintrin.h>

typedef struct {
    int width, height, max_iter, tile, threads, rot90, emit_tiles, simd, cardioid, adapter;
    double cx, cy, cw;
    int *order, n_order, *affinity, n_affinity;
} Config;

typedef struct { int index, x, y, w, h; } Tile;

/* Does the CPU have AVX2? The programs are compiled without /arch:AVX2 and use the AVX2 kernel only if available -
 * so they also run on older processors (scalar in that case). */
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#ifndef PF_AVX2_INSTRUCTIONS_AVAILABLE
#define PF_AVX2_INSTRUCTIONS_AVAILABLE 40
#endif
static int cpu_has_avx2(void) { return IsProcessorFeaturePresent(PF_AVX2_INSTRUCTIONS_AVAILABLE) != 0; }
#else
static int cpu_has_avx2(void) { return __builtin_cpu_supports("avx2"); }
#endif

/* ---- tiny JSON reader for the flat configuration ---- */
static const char *json_raw(const char *json, const char *key) {
    char pat[64];
    snprintf(pat, sizeof pat, "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p) return NULL;
    p = strchr(p + strlen(pat), ':');
    if (!p) return NULL;
    p++;
    while (*p == ' ') p++;
    return p;
}
static double json_num(const char *json, const char *key) {
    const char *p = json_raw(json, key);
    if (!p) { fprintf(stderr, "Field %s missing\n", key); exit(2); }
    return strtod(p, NULL);
}
static int json_flag(const char *json, const char *key) {
    const char *p = json_raw(json, key);
    return p && strncmp(p, "true", 4) == 0;
}
static int *json_list(const char *json, const char *key, int *n) {
    const char *p = json_raw(json, key);
    *n = 0;
    if (!p || *p != '[') return NULL;
    int cap = 64, *out = (int *)malloc(cap * sizeof(int));
    p++;
    while (*p && *p != ']') {
        char *end;
        long v = strtol(p, &end, 10);
        if (end == p) { p++; continue; }
        if (*n == cap) out = (int *)realloc(out, (cap *= 2) * sizeof(int));
        out[(*n)++] = (int)v;
        p = end;
    }
    return out;
}
static Config read_config(void) {
    size_t cap = 1 << 16, len = 0;
    char *buf = (char *)malloc(cap);
    size_t r;
    while ((r = fread(buf + len, 1, cap - len - 1, stdin)) > 0) {
        len += r;
        if (len + 1 >= cap) buf = (char *)realloc(buf, cap *= 2);
    }
    buf[len] = 0;
    Config c;
    c.width = (int)json_num(buf, "width");
    c.height = (int)json_num(buf, "height");
    c.max_iter = (int)json_num(buf, "maxIter");
    c.tile = (int)json_num(buf, "tile");
    c.cx = json_num(buf, "cx");
    c.cy = json_num(buf, "cy");
    c.cw = json_num(buf, "cw");
    c.rot90 = json_flag(buf, "rot90");
    c.threads = (int)json_num(buf, "threads");
    c.emit_tiles = json_flag(buf, "emitTiles");
    c.simd = json_flag(buf, "simd");
    c.cardioid = json_flag(buf, "cardioid");
    {   /* optional: graphics adapter index (GPU program only); missing or null -> -1 = default adapter */
        const char *p = json_raw(buf, "adapter");
        c.adapter = (p && (*p == '-' || (*p >= '0' && *p <= '9'))) ? atoi(p) : -1;
    }
    c.order = json_list(buf, "order", &c.n_order);
    c.affinity = json_list(buf, "affinity", &c.n_affinity);
    free(buf);
    return c;
}

/* ---- color palette like _palette() in mandelbrot.py ---- */
#define PAL_N 1024
static unsigned char PALETTE[PAL_N * 3];
static void build_palette(void) {
    static const double stops[6] = {0.0, 0.16, 0.42, 0.6425, 0.8575, 1.0};
    static const double cols[6][3] = {{0, 7, 100}, {32, 107, 203}, {237, 255, 255}, {255, 170, 0}, {0, 2, 0}, {0, 7, 100}};
    for (int i = 0; i < PAL_N; i++) {
        double tt = (double)i / PAL_N;
        int j = 0;
        while (j < 4 && tt > stops[j + 1]) j++;
        for (int k = 0; k < 3; k++) {
            double slope = (cols[j + 1][k] - cols[j][k]) / (stops[j + 1] - stops[j]);
            PALETTE[i * 3 + k] = (unsigned char)(slope * (tt - stops[j]) + cols[j][k]);
        }
    }
}

static inline void store_px(unsigned char *rgb, int p, double nu, int64_t *inside, double *sum) {
    if (nu < 0) { (*inside)++; rgb[p] = rgb[p + 1] = rgb[p + 2] = 0; return; }
    *sum += nu;
    int idx = (int)((int64_t)(sqrt(nu) * 64) % PAL_N) * 3;
    rgb[p] = PALETTE[idx]; rgb[p + 1] = PALETTE[idx + 1]; rgb[p + 2] = PALETTE[idx + 2];
}

/* smoothed value from escape step and |z|^2 at escape; -1 = inside the set */
static inline double smooth(int64_t it, double r2) {
    return it < 0 ? -1.0 : (double)(it + 1) - log2(0.5 * log(r2));
}

static inline void coords(const Config *c, int px, int py, double *cr, double *ci) {
    double scale = c->cw / c->width;
    double sx = (((double)px - c->width / 2.0) + 0.5) * scale;
    double sy = (((double)py - c->height / 2.0) + 0.5) * scale;
    if (c->rot90) { *cr = c->cx + sy; *ci = c->cy + sx; }   /* rotated: right = +Im, down = +Re */
    else          { *cr = c->cx + sx; *ci = c->cy - sy; }
}

/* Main cardioid or the period-2 bulb to its left: certainly inside the set (same formula as mandelbrot.py) */
static inline int in_main_bulbs(double x, double y) {
    double xm = x - 0.25, y2 = y * y, q = xm * xm + y2;
    return q * (q + xm) <= 0.25 * y2 || (x + 1.0) * (x + 1.0) + y2 <= 0.0625;
}

/* ---- scalar: pixel by pixel ---- */
static void render_scalar(const Tile *t, const Config *c, unsigned char *rgb, int64_t *inside, double *sum) {
    for (int y = 0; y < t->h; y++)
        for (int x = 0; x < t->w; x++) {
            double cr, ci, zr = 0, zi = 0, r2 = 0;
            int64_t esc = -1;
            coords(c, t->x + x, t->y + y, &cr, &ci);
            int max_iter = c->cardioid && in_main_bulbs(cr, ci) ? 0 : c->max_iter;   /* inside the set: do not iterate */
            for (int it = 0; it < max_iter; it++) {
                double zr2 = zr * zr, zi2 = zi * zi;
                if (zr2 + zi2 > 256.0) { esc = it; r2 = zr2 + zi2; break; }
                zi = 2.0 * zr * zi + ci;
                zr = zr2 - zi2 + cr;
            }
            store_px(rgb, (y * t->w + x) * 3, smooth(esc, r2), inside, sum);
        }
}

/* ---- 4 pixels at once: the kernel runs the iteration and returns escape step and |z|^2 per lane ----
 * active = bit mask of the lanes to compute (bit l = lane l); the others count as "inside the set". */
typedef void (*Kernel4)(const double *cr, const double *ci, int max_iter, int64_t *esc_it, double *esc_r2, unsigned active);

/* AVX2 with intrinsics (C/C++). Same operations in the same order as scalar, no FMA. */
static void kernel4_intrin(const double *cr4, const double *ci4, int max_iter, int64_t *esc_it, double *esc_r2, unsigned active) {
    __m256d cr = _mm256_loadu_pd(cr4), ci = _mm256_loadu_pd(ci4);
    __m256d zr = _mm256_setzero_pd(), zi = _mm256_setzero_pd();
    const __m256d limit = _mm256_set1_pd(256.0), two = _mm256_set1_pd(2.0);
    for (int l = 0; l < 4; l++) esc_it[l] = -1;
    if (!active) return;
    for (int it = 0; it < max_iter; it++) {
        __m256d zr2 = _mm256_mul_pd(zr, zr), zi2 = _mm256_mul_pd(zi, zi);
        __m256d r2 = _mm256_add_pd(zr2, zi2);
        unsigned done = (unsigned)_mm256_movemask_pd(_mm256_cmp_pd(r2, limit, _CMP_GT_OQ)) & active;
        if (done) {
            double tmp[4];
            _mm256_storeu_pd(tmp, r2);
            for (int l = 0; l < 4; l++)
                if (done >> l & 1) { esc_it[l] = it; esc_r2[l] = tmp[l]; }
            active &= ~done;
            if (!active) break;
        }
        zi = _mm256_add_pd(_mm256_mul_pd(_mm256_mul_pd(two, zr), zi), ci);
        zr = _mm256_add_pd(_mm256_sub_pd(zr2, zi2), cr);
    }
}

#ifdef USE_ASM
/* hand-written AVX2 kernel, see asm/kernel.asm */
#ifdef __cplusplus
extern "C"
#endif
void mandel4_asm(const double *cr, const double *ci, int max_iter, int64_t *esc_it, double *esc_r2, unsigned active);
#endif

static void render_simd(const Tile *t, const Config *c, Kernel4 k4, unsigned char *rgb, int64_t *inside, double *sum) {
    for (int y = 0; y < t->h; y++) {
        int x = 0;
        for (; x + 4 <= t->w; x += 4) {
            double cr[4], ci[4], r2[4] = {0, 0, 0, 0};
            int64_t esc[4];
            unsigned active = 0xF;
            for (int l = 0; l < 4; l++) {
                coords(c, t->x + x + l, t->y + y, &cr[l], &ci[l]);
                if (c->cardioid && in_main_bulbs(cr[l], ci[l])) active &= ~(1u << l);   /* certainly inside the set */
            }
            k4(cr, ci, c->max_iter, esc, r2, active);
#pragma loop(no_vector)   /* do not turn into vector math functions: those would differ in the last digit */
            for (int l = 0; l < 4; l++) store_px(rgb, (y * t->w + x + l) * 3, smooth(esc[l], r2[l]), inside, sum);
        }
        for (; x < t->w; x++) {   /* remainder of a row: scalar */
            Tile one = {0, t->x + x, t->y + y, 1, 1};
            unsigned char px[3];
            render_scalar(&one, c, px, inside, sum);
            memcpy(rgb + (y * t->w + x) * 3, px, 3);
        }
    }
}

/* number tiles as in mandelbrot.py */
static Tile *make_tiles(const Config *c, int *n) {
    int cols = (c->width + c->tile - 1) / c->tile, rows = (c->height + c->tile - 1) / c->tile;
    Tile *t = (Tile *)malloc(sizeof(Tile) * cols * rows);
    *n = 0;
    for (int y = 0; y < c->height; y += c->tile)
        for (int x = 0; x < c->width; x += c->tile) {
            Tile tt = {*n, x, y, c->tile < c->width - x ? c->tile : c->width - x, c->tile < c->height - y ? c->tile : c->height - y};
            t[(*n)++] = tt;
        }
    return t;
}
