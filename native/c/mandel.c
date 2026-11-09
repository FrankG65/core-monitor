/* Mandelbrot in C with native threads (Windows: CreateThread, Linux: POSIX threads) and a shared tile queue
 * (atomic increment); the operating-system calls are in platform.h.
 * When compiled with /DUSE_ASM, the hand-written assembler kernel is used instead of the intrinsics kernel.
 * Protocol as in csharp/MandelBench: READY, per tile "B i worker cpu ms len" + RGB bytes, at the end "R {json}".
 */
#include "../platform.h"
#include "../mandel_core.h"

static Config cfg;
static Tile *tiles;
static int n_tiles, *order;
static km_counter next_tile = -1;
static km_lock out_lock;
static int64_t total_inside;
static double total_sum, total_cpu;
static int threads_seen;
static Kernel4 kernel;
#define now km_now

static KM_THREAD_FN worker(KM_THREAD_ARG arg) {
    int index = (int)(intptr_t)arg;
    if (cfg.n_affinity > 0)
        km_pin_thread(cfg.affinity[index % cfg.n_affinity]);
    int64_t inside = 0;
    double sum = 0, cpu = 0;
    long k;
    while ((k = km_increment(&next_tile)) < n_tiles) {
        const Tile *t = &tiles[order[k]];
        double t0 = now();
        unsigned char *rgb = (unsigned char *)malloc((size_t)t->w * t->h * 3);
        if (kernel) render_simd(t, &cfg, kernel, rgb, &inside, &sum);
        else render_scalar(t, &cfg, rgb, &inside, &sum);
        double sec = now() - t0;
        cpu += sec;
        if (cfg.emit_tiles) {
            km_lock_enter(&out_lock);
            fprintf(stdout, "B %d %d %lu %.1f %d\n", t->index, index, km_current_cpu(), sec * 1000, t->w * t->h * 3);
            fwrite(rgb, 1, (size_t)t->w * t->h * 3, stdout);
            fflush(stdout);
            km_lock_leave(&out_lock);
        }
        free(rgb);
    }
    km_lock_enter(&out_lock);
    total_inside += inside; total_sum += sum; total_cpu += cpu; threads_seen++;
    km_lock_leave(&out_lock);
    return KM_THREAD_RET;
}

int main(void) {
    km_binary_stdout();   /* write image data unchanged */
    cfg = read_config();
    km_below_normal();    /* like the other compute cores */
    build_palette();
    km_lock_init(&out_lock);
#ifdef USE_ASM
    if (!cpu_has_avx2()) { fprintf(stderr, "This CPU has no AVX2 - the assembler kernel requires it.\n"); return 5; }
    kernel = mandel4_asm;   /* assembler variant always computes 4 pixels at once */
#else
    kernel = cfg.simd && cpu_has_avx2() ? kernel4_intrin : NULL;   /* without AVX2: scalar */
#endif
    tiles = make_tiles(&cfg, &n_tiles);
    if (cfg.n_order > 0) order = cfg.order;
    else {
        order = (int *)malloc(sizeof(int) * n_tiles);
        for (int i = 0; i < n_tiles; i++) order[i] = i;
        cfg.n_order = n_tiles;
    }

    /* warm-up (load the program's pages, run the kernel once), then READY */
    { Config w = cfg; w.width = 8; w.height = 4; w.max_iter = 50; Tile t = {0, 0, 0, 8, 4};
      unsigned char px[96]; int64_t i = 0; double s = 0;
      if (kernel) render_simd(&t, &w, kernel, px, &i, &s); else render_scalar(&t, &w, px, &i, &s); }
    fprintf(stdout, kernel ? "READY simd\n" : "READY\n");
    fflush(stdout);

    double t0 = now();
    km_thread *h = (km_thread *)malloc(sizeof(km_thread) * cfg.threads);
    for (int i = 0; i < cfg.threads; i++) km_thread_start(&h[i], worker, (void *)(intptr_t)i);
    for (int i = 0; i < cfg.threads; i++) km_thread_join(h[i]);
    double seconds = now() - t0;
    fprintf(stdout, "R {\"seconds\":%.6f,\"cpu_time\":%.6f,\"inside\":%lld,\"sum_nu\":%.10f,\"threads_seen\":%d,\"simd\":%s}\n",
            seconds, total_cpu, (long long)total_inside, total_sum, threads_seen, kernel ? "true" : "false");
    fflush(stdout);
    return 0;
}
