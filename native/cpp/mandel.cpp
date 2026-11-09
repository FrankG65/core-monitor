// Mandelbrot in C++ with std::thread and std::atomic as a shared tile queue.
// Same compute core as the C variant (mandel_core.h); only the threading and I/O side is C++.
// Protocol as in csharp/MandelBench: READY, per tile "B i worker cpu ms len" + RGB bytes, at the end "R {json}".
#include "../platform.h"   // pinning, processor number, priority, binary stdout (Windows/Linux)
#include <atomic>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <numeric>
#include <thread>
#include <vector>
#include "../mandel_core.h"

int main() {
    km_binary_stdout();   // write image data unchanged
    Config cfg = read_config();
    km_below_normal();
    build_palette();
    Kernel4 kernel = cfg.simd && cpu_has_avx2() ? kernel4_intrin : nullptr;   // without AVX2: scalar

    int n_tiles = 0;
    Tile *tiles = make_tiles(&cfg, &n_tiles);
    std::vector<int> order(cfg.order, cfg.order + cfg.n_order);
    if (order.empty()) { order.resize(n_tiles); std::iota(order.begin(), order.end(), 0); }

    {   // warm-up, then READY
        Config w = cfg; w.width = 8; w.height = 4; w.max_iter = 50;
        Tile t{0, 0, 0, 8, 4}; unsigned char px[96]; int64_t i = 0; double s = 0;
        kernel ? render_simd(&t, &w, kernel, px, &i, &s) : render_scalar(&t, &w, px, &i, &s);
    }
    std::printf(kernel ? "READY simd\n" : "READY\n");
    std::fflush(stdout);

    std::atomic<int> next{0};
    std::mutex out;
    int64_t total_inside = 0;
    double total_sum = 0, total_cpu = 0;
    int seen = 0;
    using clock = std::chrono::steady_clock;

    auto worker = [&](int index) {
        if (cfg.n_affinity > 0)
            km_pin_thread(cfg.affinity[index % cfg.n_affinity]);
        int64_t inside = 0;
        double sum = 0, cpu = 0;
        for (int k; (k = next.fetch_add(1, std::memory_order_relaxed)) < (int)order.size();) {
            const Tile &t = tiles[order[k]];
            auto t0 = clock::now();
            std::vector<unsigned char> rgb(size_t(t.w) * t.h * 3);
            kernel ? render_simd(&t, &cfg, kernel, rgb.data(), &inside, &sum)
                   : render_scalar(&t, &cfg, rgb.data(), &inside, &sum);
            double sec = std::chrono::duration<double>(clock::now() - t0).count();
            cpu += sec;
            if (cfg.emit_tiles) {
                std::lock_guard<std::mutex> g(out);
                std::fprintf(stdout, "B %d %d %lu %.1f %zu\n", t.index, index, km_current_cpu(), sec * 1000, rgb.size());
                std::fwrite(rgb.data(), 1, rgb.size(), stdout);
                std::fflush(stdout);
            }
        }
        std::lock_guard<std::mutex> g(out);
        total_inside += inside; total_sum += sum; total_cpu += cpu; seen++;
    };

    auto t0 = clock::now();
    std::vector<std::thread> pool;
    for (int i = 0; i < cfg.threads; i++) pool.emplace_back(worker, i);
    for (auto &th : pool) th.join();
    double seconds = std::chrono::duration<double>(clock::now() - t0).count();

    std::printf("R {\"seconds\":%.6f,\"cpu_time\":%.6f,\"inside\":%lld,\"sum_nu\":%.10f,\"threads_seen\":%d,\"simd\":%s}\n",
                seconds, total_cpu, (long long)total_inside, total_sum, seen, kernel ? "true" : "false");
    std::fflush(stdout);
    return 0;
}
