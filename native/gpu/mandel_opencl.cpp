// Mandelbrot on the graphics card: C++ host program for the OpenCL kernel mandel.cl (Linux).
// Counterpart to mandel_gpu.cpp (Direct3D 11, Windows) with the same protocol: READY, "B ..." per tile,
// "R {json}", plus a line "I {json}" with the name and capabilities of the graphics card, and --probe.
//
// Flow: choose the device, build the kernel (counts as startup, like process startup in Python). Then compute
// the image in bands of one tile row each. While the GPU computes band k+1, the CPU reads back band k and colors
// it with several threads (same formula as everywhere).
//
// OpenCL lists every installed driver: graphics cards (NVIDIA, AMD ROCm/Mesa, Intel) and CPU drivers such as
// POCL. CPU drivers count as "software" (not used), unless KM_OPENCL_CPU=1 is set (used by the automatic tests).
#define CL_TARGET_OPENCL_VERSION 120
#include <CL/cl.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>
#include "../platform.h"
#include "../mandel_core.h"

using clk = std::chrono::steady_clock;
static double secs(clk::time_point a, clk::time_point b) { return std::chrono::duration<double>(b - a).count(); }
static void fail(const char *what, cl_int err) { std::fprintf(stderr, "%s failed (OpenCL error %d)\n", what, (int)err); std::exit(3); }
#define CHECK(call, what) do { cl_int e_ = (call); if (e_ != CL_SUCCESS) fail(what, e_); } while (0)

static std::string json_escape(const std::string &s) {
    std::string out;
    for (char ch : s) {
        if (ch == '"' || ch == '\\') out += '\\';
        if ((unsigned char)ch >= 32) out += ch;
    }
    return out;
}
static std::string dev_str(cl_device_id d, cl_device_info what) {
    size_t n = 0;
    clGetDeviceInfo(d, what, 0, nullptr, &n);
    std::string s(n, '\0');
    clGetDeviceInfo(d, what, n, s.data(), nullptr);
    while (!s.empty() && (s.back() == '\0' || s.back() == ' ')) s.pop_back();
    return s;
}
template <class T> static T dev_val(cl_device_id d, cl_device_info what) {
    T v{};
    clGetDeviceInfo(d, what, sizeof v, &v, nullptr);
    return v;
}

// all OpenCL devices of all platforms, numbered across platforms (= "index" of --probe and "adapter")
static std::vector<cl_device_id> all_devices() {
    std::vector<cl_device_id> out;
    cl_uint np = 0;
    if (clGetPlatformIDs(0, nullptr, &np) != CL_SUCCESS || np == 0) return out;
    std::vector<cl_platform_id> ps(np);
    clGetPlatformIDs(np, ps.data(), nullptr);
    for (auto p : ps) {
        cl_uint nd = 0;
        if (clGetDeviceIDs(p, CL_DEVICE_TYPE_ALL, 0, nullptr, &nd) != CL_SUCCESS || nd == 0) continue;
        std::vector<cl_device_id> ds(nd);
        clGetDeviceIDs(p, CL_DEVICE_TYPE_ALL, nd, ds.data(), nullptr);
        out.insert(out.end(), ds.begin(), ds.end());
    }
    return out;
}
static bool is_software(cl_device_id d) {
    bool cpu = (dev_val<cl_device_type>(d, CL_DEVICE_TYPE) & CL_DEVICE_TYPE_CPU) != 0;
    const char *allow = std::getenv("KM_OPENCL_CPU");
    return cpu && !(allow && std::strcmp(allow, "1") == 0);
}
static bool has_double(cl_device_id d) { return dev_val<cl_device_fp_config>(d, CL_DEVICE_DOUBLE_FP_CONFIG) != 0; }

// --probe: list all devices (name, vendor, memory, driver, OpenCL version, double)
static int probe() {
    auto ds = all_devices();
    std::printf("{\"adapters\":[");
    for (size_t i = 0; i < ds.size(); i++) {
        cl_device_id d = ds[i];
        std::string ver = dev_str(d, CL_DEVICE_VERSION);    // e.g. "OpenCL 3.0 CUDA"
        std::string api = ver.substr(0, ver.find(' ', 7));   // "OpenCL 3.0"
        bool cpu = (dev_val<cl_device_type>(d, CL_DEVICE_TYPE) & CL_DEVICE_TYPE_CPU) != 0;
        bool unified = dev_val<cl_bool>(d, CL_DEVICE_HOST_UNIFIED_MEMORY) != 0;   // integrated graphics / CPU
        unsigned long long mem = dev_val<cl_ulong>(d, CL_DEVICE_GLOBAL_MEM_SIZE) >> 20;
        std::printf("%s{\"index\":%zu,\"name\":\"%s\",\"vendor_id\":%u,\"vram_mb\":%llu,\"shared_mb\":%llu,"
                    "\"driver\":\"%s\",\"feature_level\":\"%s\",\"api\":\"%s\",\"compute\":true,\"double\":%s,"
                    "\"software\":%s,\"cpu_device\":%s}",
                    i ? "," : "", i, json_escape(dev_str(d, CL_DEVICE_NAME)).c_str(), dev_val<cl_uint>(d, CL_DEVICE_VENDOR_ID),
                    unified ? 0ULL : mem, unified ? mem : 0ULL, json_escape(dev_str(d, CL_DRIVER_VERSION)).c_str(),
                    json_escape(ver).c_str(), json_escape(api).c_str(), has_double(d) ? "true" : "false",
                    is_software(d) ? "true" : "false", cpu ? "true" : "false");
    }
    std::printf("]}\n");
    return 0;
}

static std::string exe_dir() {
    char buf[4096];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
    if (n <= 0) return "./";
    std::string p(buf, n);
    return p.substr(0, p.find_last_of('/') + 1);
}

int main(int argc, char **argv) {
    if (argc > 1 && std::strcmp(argv[1], "--probe") == 0) return probe();
    Config cfg = read_config();
    km_below_normal();
    build_palette();
    const bool useFloat = std::getenv("MANDEL_GPU_FLOAT") != nullptr || cfg.simd;   // simd field = float variant

    // ---- choose the device: the one chosen by the server (adapter), otherwise the first usable graphics card ----
    auto ds = all_devices();
    cl_device_id dev = nullptr;
    if (cfg.adapter >= 0 && (size_t)cfg.adapter < ds.size()) dev = ds[cfg.adapter];
    else for (auto d : ds) if (!is_software(d)) { dev = d; break; }
    if (!dev) { std::fprintf(stderr, "No OpenCL graphics card found\n"); return 4; }
    if (!useFloat && !has_double(dev)) { std::fprintf(stderr, "Graphics card does not support double\n"); return 4; }
    cl_int err;
    cl_context ctx = clCreateContext(nullptr, 1, &dev, nullptr, nullptr, &err);
    if (!ctx) fail("clCreateContext", err);
    cl_command_queue q = clCreateCommandQueue(ctx, dev, 0, &err);   // in order: kernel b, read b, kernel b+1, read b+1
    if (!q) fail("clCreateCommandQueue", err);

    // ---- build the kernel from mandel.cl next to the program ----
    std::ifstream src(exe_dir() + "mandel.cl");
    if (!src) { std::fprintf(stderr, "mandel.cl not found next to the program\n"); return 3; }
    std::stringstream ss;
    ss << src.rdbuf();
    std::string code = ss.str();
    const char *codep = code.c_str();
    cl_program prog = clCreateProgramWithSource(ctx, 1, &codep, nullptr, &err);
    if (!prog) fail("clCreateProgramWithSource", err);
    const char *opts = useFloat ? "-D REAL=float -D USE_FLOAT=1" : "-D REAL=double";
    if (clBuildProgram(prog, 1, &dev, opts, nullptr, nullptr) != CL_SUCCESS) {
        size_t n = 0;
        clGetProgramBuildInfo(prog, dev, CL_PROGRAM_BUILD_LOG, 0, nullptr, &n);
        std::string log(n, '\0');
        clGetProgramBuildInfo(prog, dev, CL_PROGRAM_BUILD_LOG, n, log.data(), nullptr);
        std::fprintf(stderr, "%s\n", log.c_str());
        fail("Kernel compilation", CL_BUILD_PROGRAM_FAILURE);
    }
    cl_kernel kern = clCreateKernel(prog, "mandel", &err);
    if (!kern) fail("clCreateKernel", err);

    // ---- buffers: two sets, each for one band (one tile row) ----
    const unsigned W = cfg.width, H = cfg.height, band = cfg.tile, n = W * band;
    const size_t rsize = useFloat ? sizeof(float) : sizeof(double);
    struct Slot { cl_mem it, r2; std::vector<int> hit; std::vector<unsigned char> hr2; cl_event done; unsigned y0, rows; };
    Slot slots[2];
    for (auto &s : slots) {
        s.it = clCreateBuffer(ctx, CL_MEM_WRITE_ONLY, n * sizeof(int), nullptr, &err);
        if (!s.it) fail("clCreateBuffer", err);
        s.r2 = clCreateBuffer(ctx, CL_MEM_WRITE_ONLY, n * rsize, nullptr, &err);
        if (!s.r2) fail("clCreateBuffer", err);
        s.hit.resize(n);
        s.hr2.resize(n * rsize);
        s.done = nullptr;
    }
    double cx = cfg.cx, cy = cfg.cy, scale = cfg.cw / cfg.width;
    cl_uint uW = W, uH = H, maxIter = cfg.max_iter, rot = cfg.rot90, card = cfg.cardioid;
    auto dispatch = [&](Slot &s, unsigned y0, cl_uint iters) {
        s.y0 = y0;
        s.rows = std::min(band, H - y0);
        cl_uint uy0 = s.y0, urows = s.rows;
        clSetKernelArg(kern, 0, sizeof(cl_mem), &s.it);
        clSetKernelArg(kern, 1, sizeof(cl_mem), &s.r2);
        clSetKernelArg(kern, 2, sizeof(double), &cx);
        clSetKernelArg(kern, 3, sizeof(double), &cy);
        clSetKernelArg(kern, 4, sizeof(double), &scale);
        clSetKernelArg(kern, 5, sizeof(cl_uint), &uW);
        clSetKernelArg(kern, 6, sizeof(cl_uint), &uH);
        clSetKernelArg(kern, 7, sizeof(cl_uint), &iters);
        clSetKernelArg(kern, 8, sizeof(cl_uint), &rot);
        clSetKernelArg(kern, 9, sizeof(cl_uint), &uy0);
        clSetKernelArg(kern, 10, sizeof(cl_uint), &urows);
        CHECK(clSetKernelArg(kern, 11, sizeof(cl_uint), &card), "clSetKernelArg");
        size_t global[2] = {(W + 15) / 16 * 16, (s.rows + 15) / 16 * 16};
        size_t local[2] = {16, 16};
        cl_int e = clEnqueueNDRangeKernel(q, kern, 2, nullptr, global, local, 0, nullptr, nullptr);
        if (e == CL_INVALID_WORK_GROUP_SIZE) e = clEnqueueNDRangeKernel(q, kern, 2, nullptr, global, nullptr, 0, nullptr, nullptr);
        CHECK(e, "clEnqueueNDRangeKernel");
        CHECK(clEnqueueReadBuffer(q, s.it, CL_FALSE, 0, size_t(s.rows) * W * sizeof(int), s.hit.data(), 0, nullptr, nullptr), "read");
        CHECK(clEnqueueReadBuffer(q, s.r2, CL_FALSE, 0, size_t(s.rows) * W * rsize, s.hr2.data(), 0, nullptr, &s.done), "read");
        clFlush(q);
    };
    auto wait = [&](Slot &s) { clWaitForEvents(1, &s.done); clReleaseEvent(s.done); s.done = nullptr; };

    // warm-up: compute a small band (the driver finishes preparing the kernel), then READY
    dispatch(slots[0], 0, 10);
    wait(slots[0]);
    std::printf("I {\"gpu\":\"%s\",\"double\":%s,\"precision\":\"%s\"}\n", json_escape(dev_str(dev, CL_DEVICE_NAME)).c_str(),
                has_double(dev) ? "true" : "false", useFloat ? "float" : "double");
    std::printf("READY\n");
    std::fflush(stdout);

    int nTiles = 0;
    Tile *tiles = make_tiles(&cfg, &nTiles);
    const int hostThreads = std::max(1, std::min(cfg.threads, 48));
    int64_t inside = 0;
    double sum = 0, colorTime = 0, waitTime = 0;

    auto t0 = clk::now();
    const unsigned nBands = (H + band - 1) / band;
    dispatch(slots[0], 0, maxIter);
    for (unsigned b = 0; b < nBands; b++) {
        Slot &cur = slots[b & 1];
        if (b + 1 < nBands) dispatch(slots[(b + 1) & 1], (b + 1) * band, maxIter);   // GPU already computes the next band
        auto tw = clk::now();
        wait(cur);                                                                    // until band b has been read back
        auto tc = clk::now();
        waitTime += secs(tw, tc);

        // color the band row by row in parallel (rows split evenly across the threads)
        std::vector<unsigned char> bandRgb(size_t(W) * cur.rows * 3);
        int nt = std::min<int>(hostThreads, cur.rows);
        std::vector<int64_t> tin(nt, 0);
        std::vector<double> tsum(nt, 0);
        std::vector<std::thread> pool;
        for (int t = 0; t < nt; t++)
            pool.emplace_back([&, t] {
                for (unsigned y = t; y < cur.rows; y += nt)
                    for (unsigned x = 0; x < W; x++) {
                        size_t i = size_t(y) * W + x;
                        double r2;
                        if (useFloat) { float f; std::memcpy(&f, &cur.hr2[i * 4], 4); r2 = f; }
                        else std::memcpy(&r2, &cur.hr2[i * 8], 8);
                        store_px(bandRgb.data(), int(i * 3), smooth(cur.hit[i], r2), &tin[t], &tsum[t]);
                    }
            });
        for (auto &th : pool) th.join();
        for (int t = 0; t < nt; t++) { inside += tin[t]; sum += tsum[t]; }
        colorTime += secs(tc, clk::now());
        if (cfg.emit_tiles)   // split the band into tiles and output them (same format as the CPU computation methods)
            for (int k = 0; k < nTiles; k++) {
                const Tile &t = tiles[k];
                if ((unsigned)t.y != cur.y0) continue;
                std::printf("B %d 0 0 0.0 %d\n", t.index, t.w * t.h * 3);
                for (int y = 0; y < t.h; y++)
                    std::fwrite(&bandRgb[(size_t(y) * W + t.x) * 3], 1, size_t(t.w) * 3, stdout);
            }
        std::fflush(stdout);
    }
    double seconds = secs(t0, clk::now());
    std::printf("R {\"seconds\":%.6f,\"cpu_time\":%.6f,\"inside\":%lld,\"sum_nu\":%.10f,\"threads_seen\":1,\"simd\":false,"
                "\"wait_gpu\":%.6f,\"color\":%.6f}\n", seconds, colorTime, (long long)inside, sum, waitTime, colorTime);
    std::fflush(stdout);
    return 0;
}
