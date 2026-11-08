"""Start Core Monitor:  python server.py   ->  http://127.0.0.1:8000  (reachable only on this PC)

The actual application is in app.py. This file is deliberately tiny: on Windows every worker process
(Mandelbrot, Pi, load generator) starts as a new Python and loads the start file again. If the whole web server
were here, each of up to 48 workers would load FastAPI, numba etc. – that costs a lot of memory and time.
"""
import os

# numpy ships a math library (OpenBLAS) that allocates buffers for all CPU threads in EVERY process –
# measured ≈ 800 MB per worker, with 48 workers almost 40 GB. We parallelise ourselves via processes and do not
# need these inner threads. Set before numpy is first loaded so that all worker processes inherit it.
for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(var, "1")

if __name__ == "__main__":
    import app
    app.main()
