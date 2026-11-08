// Mandelbrot with real .NET threads - the counterpart to mandelbrot.py.
// Same tile layout, same formula (smoothed iteration count, escape radius 16), same color palette.
//
// Input (stdin, JSON): width, height, maxIter, tile, cx, cy, cw, rot90, threads, order[], affinity[], emitTiles, simd
//   simd = true: 4 pixels at once per thread (Vector256<double>, AVX2), otherwise pixel by pixel
// Output (stdout, line by line):
//   READY                      after warm-up (JIT); the measurement starts afterwards
//   B i worker cpu ms len      one header line per finished tile, followed directly by len bytes of RGB (binary, no base64 detour)
//   R {json}                   result: seconds, cpu_time, inside, sum_nu, threads_seen
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.Intrinsics;
using System.Text;
using System.Text.Json;

var cfg = JsonSerializer.Deserialize<Config>(Console.In.ReadToEnd(),
    new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
var stdout = Console.OpenStandardOutput();
var output = new StreamWriter(stdout, new UTF8Encoding(false), 1 << 16) { AutoFlush = true };
try { Process.GetCurrentProcess().PriorityClass = ProcessPriorityClass.BelowNormal; } catch { }  // like the Python workers

// number tiles in the same order as mandelbrot.py
var tiles = new List<Tile>();
for (int y = 0; y < cfg.Height; y += cfg.Tile)
    for (int x = 0; x < cfg.Width; x += cfg.Tile)
        tiles.Add(new Tile(tiles.Count, x, y, Math.Min(cfg.Tile, cfg.Width - x), Math.Min(cfg.Tile, cfg.Height - y)));
int[] order = cfg.Order is { Length: > 0 } o ? o : Enumerable.Range(0, tiles.Count).ToArray();

bool simd = cfg.Simd && Vector256.IsHardwareAccelerated;  // without AVX2: automatically scalar
string isa = $"AVX2={System.Runtime.Intrinsics.X86.Avx2.IsSupported} FMA={System.Runtime.Intrinsics.X86.Fma.IsSupported} " +
             $"AVX512={System.Runtime.Intrinsics.X86.Avx512F.IsSupported}";
RenderFn render = simd ? Mandel.RenderSimd : Mandel.Render;

// warm-up: the JIT compiles the compute kernel before the clock starts
render(new Tile(0, 0, 0, 8, 4), cfg with { Width = 8, Height = 4, MaxIter = 50 }, new byte[96], out _, out _);
output.WriteLine(simd ? "READY simd" : "READY");

int next = -1;
long inside = 0;
double sumNu = 0, cpuTime = 0;
var seen = new HashSet<int>();
var sync = new object();

void Worker(int index)
{
    if (cfg.Affinity is { Length: > 0 } aff)
        Native.SetThreadAffinityMask(Native.GetCurrentThread(), (UIntPtr)(1UL << aff[index % aff.Length]));
    long myInside = 0;
    double mySum = 0, myCpu = 0;
    int k;
    while ((k = Interlocked.Increment(ref next)) < order.Length)
    {
        var t = tiles[order[k]];
        long t0 = Stopwatch.GetTimestamp();
        var rgb = new byte[t.W * t.H * 3];
        render(t, cfg, rgb, out long tileInside, out double tileSum);
        double sec = Stopwatch.GetElapsedTime(t0).TotalSeconds;
        myInside += tileInside; mySum += tileSum; myCpu += sec;
        if (cfg.EmitTiles)
        {
            byte[] head = Encoding.ASCII.GetBytes(FormattableString.Invariant(
                $"B {t.Index} {index} {Native.GetCurrentProcessorNumber()} {Math.Round(sec * 1000, 1)} {rgb.Length}\n"));
            lock (sync)
            {
                stdout.Write(head);
                stdout.Write(rgb);
                stdout.Flush();
            }
        }
    }
    lock (sync) { inside += myInside; sumNu += mySum; cpuTime += myCpu; seen.Add(index); }
}

var sw = Stopwatch.StartNew();
var threads = Enumerable.Range(0, cfg.Threads).Select(i => new Thread(() => Worker(i)) { IsBackground = true }).ToList();
threads.ForEach(t => t.Start());
threads.ForEach(t => t.Join());
sw.Stop();

output.WriteLine("R " + JsonSerializer.Serialize(new
{
    seconds = sw.Elapsed.TotalSeconds, cpu_time = cpuTime, inside, sum_nu = sumNu, threads_seen = seen.Count, simd, isa,
}));

delegate void RenderFn(Tile t, Config c, byte[] rgb, out long inside, out double sumNu);

record Config(int Width, int Height, int MaxIter, int Tile, double Cx, double Cy, double Cw, bool Rot90,
              int Threads, int[]? Order, int[]? Affinity, bool EmitTiles, bool Simd, bool Cardioid);

record Tile(int Index, int X, int Y, int W, int H);

static class Mandel
{
    static readonly byte[] Palette = BuildPalette(1024);

    /// Main cardioid or the period-2 bulb to its left: certainly inside the set (same formula as mandelbrot.py)
    static bool InMainBulbs(double x, double y)
    {
        double xm = x - 0.25, y2 = y * y, q = xm * xm + y2;
        return q * (q + xm) <= 0.25 * y2 || (x + 1.0) * (x + 1.0) + y2 <= 0.0625;
    }

    /// Like _escape_numba + _colorize in mandelbrot.py; also counts points inside the set and the sum of the values.
    public static void Render(Tile t, Config c, byte[] rgb, out long inside, out double sumNu)
    {
        double scale = c.Cw / c.Width;
        inside = 0; sumNu = 0;
        for (int y = 0; y < t.H; y++)
        {
            double sy = ((t.Y + y) - c.Height / 2.0 + 0.5) * scale;
            for (int x = 0; x < t.W; x++)
            {
                double sx = ((t.X + x) - c.Width / 2.0 + 0.5) * scale;
                double cr, ci;
                if (c.Rot90) { ci = c.Cy + sx; cr = c.Cx + sy; }   // rotated: right = +Im, down = +Re
                else { cr = c.Cx + sx; ci = c.Cy - sy; }
                double zr = 0, zi = 0, nu = -1;
                int maxIter = c.Cardioid && InMainBulbs(cr, ci) ? 0 : c.MaxIter;  // inside the set: do not iterate
                for (int it = 0; it < maxIter; it++)
                {
                    double zr2 = zr * zr, zi2 = zi * zi;
                    if (zr2 + zi2 > 256.0)
                    {
                        nu = it + 1 - Math.Log2(0.5 * Math.Log(zr2 + zi2));
                        break;
                    }
                    zi = 2.0 * zr * zi + ci;
                    zr = zr2 - zi2 + cr;
                }
                Store(rgb, (y * t.W + x) * 3, nu, ref inside, ref sumNu);
            }
        }
    }

    /// Like Render, but 4 pixels of a row at once (AVX2). Each lane performs exactly the same operations
    /// in the same order (no FMA), so the same image results. Finished lanes keep running masked
    /// until all 4 are done - that is the cost when inside and outside points are mixed.
    public static void RenderSimd(Tile t, Config c, byte[] rgb, out long inside, out double sumNu)
    {
        double scale = c.Cw / c.Width;
        inside = 0; sumNu = 0;
        var limit = Vector256.Create(256.0);
        Span<double> lr = stackalloc double[4], li = stackalloc double[4], escR2 = stackalloc double[4];
        Span<int> escIt = stackalloc int[4];
        for (int y = 0; y < t.H; y++)
        {
            double sy = ((t.Y + y) - c.Height / 2.0 + 0.5) * scale;
            int x = 0;
            for (; x + 4 <= t.W; x += 4)
            {
                for (int l = 0; l < 4; l++)
                {
                    double sx = ((t.X + x + l) - c.Width / 2.0 + 0.5) * scale;
                    if (c.Rot90) { li[l] = c.Cy + sx; lr[l] = c.Cx + sy; }
                    else { lr[l] = c.Cx + sx; li[l] = c.Cy - sy; }
                    escIt[l] = -1;
                }
                var cr = Vector256.Create(lr[0], lr[1], lr[2], lr[3]);
                var ci = Vector256.Create(li[0], li[1], li[2], li[3]);
                Vector256<double> zr = Vector256<double>.Zero, zi = Vector256<double>.Zero;
                uint active = 0b1111;
                if (c.Cardioid)  // lanes in the cardioid/bulb count as finished from the start (inside the set)
                    for (int l = 0; l < 4; l++)
                        if (InMainBulbs(lr[l], li[l])) active &= ~(1u << l);
                for (int it = 0; it < c.MaxIter && active != 0; it++)
                {
                    var zr2 = zr * zr;
                    var zi2 = zi * zi;
                    var r2 = zr2 + zi2;
                    uint done = Vector256.GreaterThan(r2, limit).ExtractMostSignificantBits() & active;
                    if (done != 0)
                    {
                        for (int l = 0; l < 4; l++)
                            if ((done >> l & 1) != 0) { escIt[l] = it; escR2[l] = r2.GetElement(l); }
                        active &= ~done;
                        if (active == 0) break;
                    }
                    zi = Vector256.Create(2.0) * zr * zi + ci;
                    zr = zr2 - zi2 + cr;
                }
                for (int l = 0; l < 4; l++)
                {
                    double nu = escIt[l] < 0 ? -1 : escIt[l] + 1 - Math.Log2(0.5 * Math.Log(escR2[l]));
                    Store(rgb, (y * t.W + x + l) * 3, nu, ref inside, ref sumNu);
                }
            }
            for (; x < t.W; x++)  // remainder of a row (width not divisible by 4): scalar
            {
                var one = new Tile(0, t.X + x, t.Y + y, 1, 1);
                var px = new byte[3];
                Render(one, c, px, out long ins, out double s);
                inside += ins; sumNu += s;
                Buffer.BlockCopy(px, 0, rgb, (y * t.W + x) * 3, 3);
            }
        }
    }

    static void Store(byte[] rgb, int p, double nu, ref long inside, ref double sumNu)
    {
        if (nu < 0) { inside++; rgb[p] = rgb[p + 1] = rgb[p + 2] = 0; return; }
        sumNu += nu;
        int idx = (int)((long)(Math.Sqrt(nu) * 64) % (Palette.Length / 3)) * 3;
        rgb[p] = Palette[idx]; rgb[p + 1] = Palette[idx + 1]; rgb[p + 2] = Palette[idx + 2];
    }

    /// Cyclic color gradient like _palette() in mandelbrot.py (linear interpolation, truncated to byte)
    static byte[] BuildPalette(int n)
    {
        double[] stops = { 0.0, 0.16, 0.42, 0.6425, 0.8575, 1.0 };
        double[,] cols = { { 0, 7, 100 }, { 32, 107, 203 }, { 237, 255, 255 }, { 255, 170, 0 }, { 0, 2, 0 }, { 0, 7, 100 } };
        var pal = new byte[n * 3];
        for (int i = 0; i < n; i++)
        {
            double tt = (double)i / n;
            int j = 0;
            while (j < stops.Length - 2 && tt > stops[j + 1]) j++;
            for (int k = 0; k < 3; k++)
            {
                double slope = (cols[j + 1, k] - cols[j, k]) / (stops[j + 1] - stops[j]);
                pal[i * 3 + k] = (byte)(slope * (tt - stops[j]) + cols[j, k]);
            }
        }
        return pal;
    }
}

static class Native
{
    [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentThread();
    [DllImport("kernel32.dll")] public static extern UIntPtr SetThreadAffinityMask(IntPtr thread, UIntPtr mask);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentProcessorNumber();
}
