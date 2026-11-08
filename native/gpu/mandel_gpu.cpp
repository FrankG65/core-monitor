// Mandelbrot on the graphics card: C++ host program for the Direct3D 11 compute shader mandel.hlsl.
// Same protocol as the other compute cores (READY, "B ..." per tile, "R {json}"), plus a line
// "I {json}" with the name and capabilities of the graphics card.
//
// Flow: open the device, compile the shader (counts as startup, like process startup in Python). Then compute the
// image in bands of one tile row each. While the GPU computes band k+1, the CPU reads back band k and
// colors it with several threads (same formula as everywhere, so the double image is identical bit for bit).
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <dxgi.h>
#include <io.h>
#include <fcntl.h>
#include <chrono>
#include <string>
#include <thread>
#include <vector>
#include "../mandel_core.h"

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "d3dcompiler.lib")
#pragma comment(lib, "dxgi.lib")

struct alignas(16) Params {   // must match the cbuffer in mandel.hlsl (64 bytes)
    double cx, cy, cw, scale;
    unsigned width, height, maxIter, rot90;
    unsigned y0, rows, cardioid, pad;
};

template <class T> static void release(T *&p) { if (p) { p->Release(); p = nullptr; } }
static void fail(const char *what, HRESULT hr) { std::fprintf(stderr, "%s failed (0x%08lx)\n", what, (unsigned long)hr); std::exit(3); }
using clk = std::chrono::steady_clock;
static double secs(clk::time_point a, clk::time_point b) { return std::chrono::duration<double>(b - a).count(); }

// One set of GPU buffers for a band (two sets -> the GPU computes while the CPU reads back the previous one)
struct Slot {
    ID3D11Buffer *it = nullptr, *r2 = nullptr, *itStage = nullptr, *r2Stage = nullptr;
    ID3D11UnorderedAccessView *itUav = nullptr, *r2Uav = nullptr;
    unsigned y0 = 0, rows = 0;
};

static ID3D11Buffer *makeBuffer(ID3D11Device *dev, UINT bytes, UINT stride, bool staging) {
    D3D11_BUFFER_DESC d = {};
    d.ByteWidth = bytes;
    d.StructureByteStride = stride;
    if (staging) { d.Usage = D3D11_USAGE_STAGING; d.CPUAccessFlags = D3D11_CPU_ACCESS_READ; }
    else { d.Usage = D3D11_USAGE_DEFAULT; d.BindFlags = D3D11_BIND_UNORDERED_ACCESS; d.MiscFlags = D3D11_RESOURCE_MISC_BUFFER_STRUCTURED; }
    ID3D11Buffer *b = nullptr;
    HRESULT hr = dev->CreateBuffer(&d, nullptr, &b);
    if (FAILED(hr)) fail("CreateBuffer", hr);
    return b;
}

static std::string utf8(const wchar_t *w) {
    char buf[512];
    WideCharToMultiByte(CP_UTF8, 0, w, -1, buf, sizeof buf, nullptr, nullptr);
    std::string s(buf), out;
    for (char ch : s) { if (ch == '"' || ch == '\\') out += '\\'; out += ch; }   // for JSON
    return out;
}

// --probe: list all graphics adapters (name, vendor, memory, driver, feature level, compute shader, double)
static int probe() {
    IDXGIFactory1 *f = nullptr;
    if (FAILED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void **)&f))) { std::printf("{\"adapters\":[]}\n"); return 0; }
    std::printf("{\"adapters\":[");
    IDXGIAdapter1 *a = nullptr;
    for (UINT i = 0; f->EnumAdapters1(i, &a) != DXGI_ERROR_NOT_FOUND; i++) {
        DXGI_ADAPTER_DESC1 d;
        a->GetDesc1(&d);
        LARGE_INTEGER umd = {};
        a->CheckInterfaceSupport(__uuidof(IDXGIDevice), &umd);
        ID3D11Device *dev = nullptr;
        D3D_FEATURE_LEVEL fl = (D3D_FEATURE_LEVEL)0;
        bool ok = SUCCEEDED(D3D11CreateDevice(a, D3D_DRIVER_TYPE_UNKNOWN, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &dev, &fl, nullptr));
        D3D11_FEATURE_DATA_DOUBLES dbl = {};
        if (ok) dev->CheckFeatureSupport(D3D11_FEATURE_DOUBLES, &dbl, sizeof dbl);
        std::printf("%s{\"index\":%u,\"name\":\"%s\",\"vendor_id\":%u,\"vram_mb\":%llu,\"shared_mb\":%llu,"
                    "\"driver\":\"%u.%u.%u.%u\",\"feature_level\":\"%u.%u\",\"compute\":%s,\"double\":%s,\"software\":%s}",
                    i ? "," : "", i, utf8(d.Description).c_str(), d.VendorId,
                    (unsigned long long)(d.DedicatedVideoMemory >> 20), (unsigned long long)(d.SharedSystemMemory >> 20),
                    HIWORD(umd.HighPart), LOWORD(umd.HighPart), HIWORD(umd.LowPart), LOWORD(umd.LowPart),
                    (fl >> 12) & 0xF, (fl >> 8) & 0xF, ok && fl >= D3D_FEATURE_LEVEL_11_0 ? "true" : "false",
                    dbl.DoublePrecisionFloatShaderOps ? "true" : "false",
                    (d.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) ? "true" : "false");
        release(dev);
        release(a);
    }
    std::printf("]}\n");
    release(f);
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && std::strcmp(argv[1], "--probe") == 0) return probe();
    _setmode(_fileno(stdout), _O_BINARY);
    Config cfg = read_config();
    SetPriorityClass(GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS);
    build_palette();
    const bool useFloat = std::getenv("MANDEL_GPU_FLOAT") != nullptr || cfg.simd;   // simd field = float variant

    // ---- open the device: the graphics adapter chosen by the server (adapter), otherwise the default adapter ----
    ID3D11Device *dev = nullptr;
    ID3D11DeviceContext *ctx = nullptr;
    D3D_FEATURE_LEVEL fl;
    IDXGIAdapter1 *chosen = nullptr;
    if (cfg.adapter >= 0) {
        IDXGIFactory1 *f = nullptr;
        if (SUCCEEDED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void **)&f))) f->EnumAdapters1(cfg.adapter, &chosen);
        release(f);
    }
    HRESULT hr = D3D11CreateDevice(chosen, chosen ? D3D_DRIVER_TYPE_UNKNOWN : D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0,
                                   D3D11_SDK_VERSION, &dev, &fl, &ctx);
    release(chosen);
    if (FAILED(hr)) fail("D3D11CreateDevice", hr);
    D3D11_FEATURE_DATA_DOUBLES dbl = {};
    dev->CheckFeatureSupport(D3D11_FEATURE_DOUBLES, &dbl, sizeof dbl);
    if (!useFloat && !dbl.DoublePrecisionFloatShaderOps) { std::fprintf(stderr, "Graphics card does not support double in shaders\n"); return 4; }

    std::string gpuName = "unknown";
    { IDXGIDevice *xd = nullptr; IDXGIAdapter *ad = nullptr; DXGI_ADAPTER_DESC desc;
      if (SUCCEEDED(dev->QueryInterface(__uuidof(IDXGIDevice), (void **)&xd)) && SUCCEEDED(xd->GetAdapter(&ad)) && SUCCEEDED(ad->GetDesc(&desc))) {
          char buf[256]; WideCharToMultiByte(CP_UTF8, 0, desc.Description, -1, buf, sizeof buf, nullptr, nullptr); gpuName = buf;
      }
      release(ad); release(xd); }

    // ---- load shader: precompiled (.cso next to the program), otherwise compile from mandel.hlsl ----
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(nullptr, path, MAX_PATH);
    std::wstring dir(path);
    dir = dir.substr(0, dir.find_last_of(L"\\/") + 1);
    std::vector<char> bytecode;
    {
        FILE *f = _wfopen((dir + (useFloat ? L"mandel_float.cso" : L"mandel_double.cso")).c_str(), L"rb");
        if (f) {
            std::fseek(f, 0, SEEK_END);
            bytecode.resize(std::ftell(f));
            std::fseek(f, 0, SEEK_SET);
            std::fread(bytecode.data(), 1, bytecode.size(), f);
            std::fclose(f);
        }
    }
    if (bytecode.empty()) {
        D3D_SHADER_MACRO defsFloat[] = {{"REAL", "float"}, {"USE_FLOAT", "1"}, {nullptr, nullptr}};
        ID3DBlob *code = nullptr, *errors = nullptr;
        hr = D3DCompileFromFile((dir + L"mandel.hlsl").c_str(), useFloat ? defsFloat : nullptr, nullptr, "main", "cs_5_0",
                                D3DCOMPILE_OPTIMIZATION_LEVEL3 | D3DCOMPILE_IEEE_STRICTNESS, 0, &code, &errors);
        if (FAILED(hr)) { if (errors) std::fprintf(stderr, "%s\n", (const char *)errors->GetBufferPointer()); fail("Shader compilation", hr); }
        bytecode.assign((const char *)code->GetBufferPointer(), (const char *)code->GetBufferPointer() + code->GetBufferSize());
        release(code);
    }
    ID3D11ComputeShader *cs = nullptr;
    hr = dev->CreateComputeShader(bytecode.data(), bytecode.size(), nullptr, &cs);
    if (FAILED(hr)) fail("CreateComputeShader", hr);

    // ---- buffers: two sets, each for one band (one tile row) ----
    const unsigned W = cfg.width, H = cfg.height, band = cfg.tile, n = W * band;
    Slot slots[2];
    for (auto &s : slots) {
        s.it = makeBuffer(dev, n * 4, 4, false);
        s.r2 = makeBuffer(dev, n * 8, 8, false);
        s.itStage = makeBuffer(dev, n * 4, 4, true);
        s.r2Stage = makeBuffer(dev, n * 8, 8, true);
        D3D11_UNORDERED_ACCESS_VIEW_DESC u = {};
        u.ViewDimension = D3D11_UAV_DIMENSION_BUFFER;
        u.Format = DXGI_FORMAT_UNKNOWN;
        u.Buffer.NumElements = n;
        dev->CreateUnorderedAccessView(s.it, &u, &s.itUav);
        dev->CreateUnorderedAccessView(s.r2, &u, &s.r2Uav);
    }
    D3D11_BUFFER_DESC cd = {};
    cd.ByteWidth = sizeof(Params);
    cd.Usage = D3D11_USAGE_DEFAULT;
    cd.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
    ID3D11Buffer *cbuf = nullptr;
    if (FAILED(hr = dev->CreateBuffer(&cd, nullptr, &cbuf))) fail("CreateBuffer (parameters)", hr);
    ctx->CSSetShader(cs, nullptr, 0);
    ctx->CSSetConstantBuffers(0, 1, &cbuf);

    Params prm = {cfg.cx, cfg.cy, cfg.cw, cfg.cw / cfg.width, W, H, (unsigned)cfg.max_iter, (unsigned)cfg.rot90,
                  0, 0, (unsigned)cfg.cardioid, 0};
    auto dispatch = [&](Slot &s, unsigned y0) {
        s.y0 = y0;
        s.rows = std::min(band, H - y0);
        prm.y0 = s.y0; prm.rows = s.rows;
        ctx->UpdateSubresource(cbuf, 0, nullptr, &prm, 0, 0);
        ID3D11UnorderedAccessView *uavs[2] = {s.itUav, s.r2Uav};
        ctx->CSSetUnorderedAccessViews(0, 2, uavs, nullptr);
        ctx->Dispatch((W + 15) / 16, (s.rows + 15) / 16, 1);
        ctx->CopyResource(s.itStage, s.it);
        ctx->CopyResource(s.r2Stage, s.r2);
        ctx->Flush();
    };

    // warm-up: compute a small band (the driver finalizes shader compilation), then READY
    { Params keep = prm; prm.maxIter = 10; dispatch(slots[0], 0); D3D11_MAPPED_SUBRESOURCE m;
      ctx->Map(slots[0].itStage, 0, D3D11_MAP_READ, 0, &m); ctx->Unmap(slots[0].itStage, 0); prm = keep; }
    std::printf("I {\"gpu\":\"%s\",\"double\":%s,\"precision\":\"%s\"}\n", gpuName.c_str(),
                dbl.DoublePrecisionFloatShaderOps ? "true" : "false", useFloat ? "float" : "double");
    std::printf("READY\n");
    std::fflush(stdout);

    // tiles per tile row (band)
    int nTiles = 0;
    Tile *tiles = make_tiles(&cfg, &nTiles);
    const int hostThreads = std::max(1, std::min(cfg.threads, 48));
    int64_t inside = 0;
    double sum = 0, colorTime = 0, waitTime = 0;

    auto t0 = clk::now();
    const unsigned nBands = (H + band - 1) / band;
    dispatch(slots[0], 0);
    for (unsigned b = 0; b < nBands; b++) {
        Slot &cur = slots[b & 1];
        if (b + 1 < nBands) dispatch(slots[(b + 1) & 1], (b + 1) * band);   // GPU already computes the next band
        auto tw = clk::now();
        D3D11_MAPPED_SUBRESOURCE mi, mr;
        ctx->Map(cur.itStage, 0, D3D11_MAP_READ, 0, &mi);                  // waits until the band is finished
        ctx->Map(cur.r2Stage, 0, D3D11_MAP_READ, 0, &mr);
        auto tc = clk::now();
        waitTime += secs(tw, tc);
        const int *its = (const int *)mi.pData;
        const uint32_t *r2b = (const uint32_t *)mr.pData;

        // color the band row by row in parallel (OpenMP: threads persist, no restart per band)
        std::vector<unsigned char> bandRgb(size_t(W) * cur.rows * 3);
        int64_t bandInside = 0;
        double bandSum = 0;
#pragma omp parallel for schedule(dynamic, 4) reduction(+ : bandInside, bandSum) num_threads(hostThreads)
        for (int y = 0; y < (int)cur.rows; y++)
            for (unsigned x = 0; x < W; x++) {
                size_t i = size_t(y) * W + x;
                double r2;
                if (useFloat) { float f; std::memcpy(&f, &r2b[i * 2], 4); r2 = f; }
                else std::memcpy(&r2, &r2b[i * 2], 8);
                store_px(bandRgb.data(), int(i * 3), smooth(its[i], r2), &bandInside, &bandSum);
            }
        ctx->Unmap(cur.itStage, 0);
        ctx->Unmap(cur.r2Stage, 0);
        inside += bandInside;
        sum += bandSum;
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
