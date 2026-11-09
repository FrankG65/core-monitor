// Mandelbrot on the graphics card (OpenCL kernel, Linux) - the counterpart to mandel.hlsl (Direct3D, Windows).
// Each GPU work item computes one pixel of a band of `rows` rows starting at row y0.
// Result per point: step in which it escaped (-1 = inside the set), and |z|^2 at that moment.
// The color is computed afterwards by the CPU with the same formula as all other computation methods.
//
// REAL = double (default) or float (set when the host program builds the kernel: -D REAL=float).
// FP_CONTRACT OFF forbids the compiler to contract multiplication and addition (fma) -
// same computation steps in the same order as on the CPU.
#pragma OPENCL FP_CONTRACT OFF
#ifndef REAL
#define REAL double
#endif
#if !defined(USE_FLOAT)
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#endif
#define R(x) ((REAL)(x))   // every constant in the precision of the variant (float stays float)

__kernel void mandel(__global int *escIt, __global REAL *escR2,
                     double cx, double cy, double scale,
                     uint width, uint height, uint maxIter, uint rot90,
                     uint y0, uint rows, uint cardioid)
{
    uint px = get_global_id(0), row = get_global_id(1);
    if (px >= width || row >= rows) return;
    uint py = y0 + row;
    uint idx = row * width + px;

    // coordinates as on the CPU: ((p - width/2) + 0.5) * scale
    REAL sc = (REAL)scale;
    REAL sx = (((REAL)px - (REAL)width * R(0.5)) + R(0.5)) * sc;
    REAL sy = (((REAL)py - (REAL)height * R(0.5)) + R(0.5)) * sc;
    REAL cr, ci;
    if (rot90) { cr = (REAL)cx + sy; ci = (REAL)cy + sx; }   // rotated: right = +Im, down = +Re
    else       { cr = (REAL)cx + sx; ci = (REAL)cy - sy; }

    uint limit = maxIter;
    if (cardioid) {   // main cardioid or period-2 bulb next to it: certainly inside the set, do not iterate
        REAL xm = cr - R(0.25), y2 = ci * ci, q = xm * xm + y2, xp = cr + R(1.0);
        if (q * (q + xm) <= R(0.25) * y2 || xp * xp + y2 <= R(0.0625)) limit = 0;
    }

    REAL zr = R(0), zi = R(0), r2out = R(0);
    int esc = -1;
    for (uint it = 0; it < limit; it++) {
        REAL zr2 = zr * zr;
        REAL zi2 = zi * zi;
        REAL r2 = zr2 + zi2;
        if (r2 > R(256.0)) { esc = (int)it; r2out = r2; break; }
        REAL t = (R(2.0) * zr) * zi;
        zi = t + ci;
        zr = (zr2 - zi2) + cr;
    }
    escIt[idx] = esc;
    escR2[idx] = r2out;
}
