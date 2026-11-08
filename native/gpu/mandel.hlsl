// Mandelbrot on the graphics card (Direct3D 11 compute shader).
// Each GPU thread computes one pixel. One call ("dispatch") computes a band of `rows` rows
// starting at row y0 - this keeps each job short (Windows aborts GPU jobs after ~2 s).
// Result per point: step in which it escaped (-1 = inside the set), and |z|^2 at that moment.
// The color is computed afterwards by the CPU with the same formula as all other compute cores.
//
// REAL = double (default) or float (set at compile time).
// `precise` forbids the shader compiler to contract multiplication and addition (mad/fma) -
// same computation steps in the same order as on the CPU, so that the double image matches bit for bit.
#ifndef REAL
#define REAL double
#endif

cbuffer Params : register(b0)
{
    double cx, cy, cw, scale;              // image center, width in the complex plane, width per pixel
    uint width, height, maxIter, rot90;
    uint y0, rows, cardioid, pad;
};

RWStructuredBuffer<int>   escIt : register(u0);   // per point: escape step or -1
RWStructuredBuffer<uint2> escR2 : register(u1);   // per point: |z|^2 as bit pattern (double = 2x32 bits, float = .x)

void storeR2(uint idx, REAL r2)
{
#ifdef USE_FLOAT
    escR2[idx] = uint2(asuint(r2), 0);
#else
    uint lo, hi;
    asuint(r2, lo, hi);
    escR2[idx] = uint2(lo, hi);
#endif
}

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    uint px = id.x, row = id.y;
    if (px >= width || row >= rows) return;
    uint py = y0 + row;
    uint idx = row * width + px;

    // coordinates as on the CPU: ((p - width/2) + 0.5) * scale   (uint -> float -> REAL is exact for p < 2^24)
    precise REAL sc = (REAL)scale;
    precise REAL sx = (((REAL)(float)px - (REAL)(float)width * 0.5) + 0.5) * sc;
    precise REAL sy = (((REAL)(float)py - (REAL)(float)height * 0.5) + 0.5) * sc;
    precise REAL cr, ci;
    if (rot90) { cr = (REAL)cx + sy; ci = (REAL)cy + sx; }   // rotated: right = +Im, down = +Re
    else       { cr = (REAL)cx + sx; ci = (REAL)cy - sy; }

    uint limit = maxIter;
    if (cardioid)   // main cardioid or period-2 bulb next to it: certainly inside the set, do not iterate
    {
        precise REAL xm = cr - 0.25;
        precise REAL y2 = ci * ci;
        precise REAL q = xm * xm + y2;
        precise REAL xp = cr + 1.0;
        if (q * (q + xm) <= 0.25 * y2 || xp * xp + y2 <= 0.0625) limit = 0;
    }

    precise REAL zr = 0, zi = 0, r2out = 0;
    int esc = -1;
    for (uint it = 0; it < limit; it++)
    {
        precise REAL zr2 = zr * zr;
        precise REAL zi2 = zi * zi;
        precise REAL r2 = zr2 + zi2;
        if (r2 > 256.0) { esc = (int)it; r2out = r2; break; }
        precise REAL t = (2.0 * zr) * zi;
        zi = t + ci;
        zr = (zr2 - zi2) + cr;
    }
    escIt[idx] = esc;
    storeR2(idx, r2out);
}
