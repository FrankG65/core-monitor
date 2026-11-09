// Mandelbrot: controls, drawing tiles live, scaling test with chart

// The 13 computation methods: name, kind (short form for the selection), description, short name for the chart.
// OS_LINUX: the server runs on Linux (POSIX threads, NASM, OpenCL instead of Win32 threads, MASM, Direct3D)
const OS_LINUX = () => typeof info !== "undefined" && info && info.os === "linux";
const ENGINE_INFO = {
  numba:       { name: "Python + numba", kind: L("Prozesse, 1 Pixel je Schritt", "processes, 1 pixel per step"), short: "numba",
                 desc: L("Python, von numba in Maschinencode übersetzt. Wegen des GIL rechnet je Kern ein eigener Prozess; jeder rechnet einen Bildpunkt nach dem anderen.",
                         "Python, compiled to machine code by numba. Because of the GIL, each core gets its own process; each one computes one pixel after the other.") },
  numpy:       { name: "Python + numpy", kind: L("Prozesse, Feldrechnung", "processes, array computation"), short: "numpy",
                 desc: L("Reines Python mit numpy: rechnet ganze Kacheln als Zahlenfelder. Ohne Übersetzer, deshalb die langsamste Variante.",
                         "Plain Python with numpy: computes whole tiles as arrays of numbers. No compiler, which makes it the slowest variant.") },
  csharp:      { name: "C# / .NET", kind: L("Threads, 1 Pixel je Schritt", "threads, 1 pixel per step"), short: "C#",
                 desc: L("C# (.NET 10) mit echten Threads in einem einzigen Prozess; Bildpunkt für Bildpunkt.",
                         "C# (.NET 10) with real threads in a single process; pixel by pixel.") },
  csharp_simd: { name: "C# / .NET + SIMD", kind: L("Threads, 4 Pixel gleichzeitig", "threads, 4 pixels at once"), short: "C# SIMD",
                 desc: L("Wie C#, aber jeder Thread rechnet 4 Bildpunkte gleichzeitig (AVX2-Befehle, Vector256<double>).",
                         "Like C#, but each thread computes 4 pixels at once (AVX2 instructions, Vector256<double>).") },
  rust:        { name: "Rust", kind: L("Threads, 1 Pixel je Schritt", "threads, 1 pixel per step"), short: "Rust",
                 desc: L("Rust mit echten Threads und gemeinsamer Kachel-Warteschlange; Bildpunkt für Bildpunkt.",
                         "Rust with real threads and a shared tile queue; pixel by pixel.") },
  rust_simd:   { name: "Rust + SIMD", kind: L("Threads, 4 Pixel gleichzeitig", "threads, 4 pixels at once"), short: "Rust SIMD",
                 desc: L("Rust, jeder Thread rechnet 4 Bildpunkte gleichzeitig mit AVX2-Befehlen.",
                         "Rust, each thread computes 4 pixels at once with AVX2 instructions.") },
  c:           { name: "C", kind: L("Threads, 1 Pixel je Schritt", "threads, 1 pixel per step"), short: "C",
                 get desc() { return OS_LINUX() ? L("C mit POSIX-Threads (pthread_create); Bildpunkt für Bildpunkt.",
                                                    "C with POSIX threads (pthread_create); pixel by pixel.")
                                                : L("C mit Windows-Threads (CreateThread); Bildpunkt für Bildpunkt.",
                                                    "C with Windows threads (CreateThread); pixel by pixel."); } },
  c_simd:      { name: "C + SIMD", kind: L("Threads, 4 Pixel gleichzeitig", "threads, 4 pixels at once"), short: "C SIMD",
                 desc: L("C, jeder Thread rechnet 4 Bildpunkte gleichzeitig (AVX2-Intrinsics).",
                         "C, each thread computes 4 pixels at once (AVX2 intrinsics).") },
  cpp:         { name: "C++", kind: L("Threads, 1 Pixel je Schritt", "threads, 1 pixel per step"), short: "C++",
                 desc: L("C++ mit std::thread und std::atomic; Bildpunkt für Bildpunkt.",
                         "C++ with std::thread and std::atomic; pixel by pixel.") },
  cpp_simd:    { name: "C++ + SIMD", kind: L("Threads, 4 Pixel gleichzeitig", "threads, 4 pixels at once"), short: "C++ SIMD",
                 desc: L("C++, jeder Thread rechnet 4 Bildpunkte gleichzeitig (AVX2-Intrinsics).",
                         "C++, each thread computes 4 pixels at once (AVX2 intrinsics).") },
  asm:         { name: "Assembler", kind: L("Threads, 4 Pixel gleichzeitig", "threads, 4 pixels at once"), short: "Assembler",
                 desc: L("Handgeschriebener x64-Assembler (AVX2, 4 Bildpunkte gleichzeitig) für die innere Schleife; Threads und Ein-/Ausgabe in C.",
                         "Hand-written x64 assembler (AVX2, 4 pixels at once) for the inner loop; threads and input/output in C.") },
  gpu:         { name: "GPU (double)", kind: L("Grafikkarte, doppelte Genauigkeit", "graphics card, double precision"), short: "GPU double",
                 get desc() { const api = OS_LINUX() ? L("einen OpenCL-Kernel", "an OpenCL kernel") : L("einen Direct3D-Compute-Shader", "a Direct3D compute shader");
                   return L(`Grafikkarte über ${api}: Tausende GPU-Recheneinheiten, je Bildpunkt eine. Doppelte Genauigkeit wie die CPU, trotzdem weichen einzelne Pixel ab (der Grafiktreiber übersetzt das Programm auf eigene Weise); auf Spiele-Grafikkarten langsam.`,
                            `Graphics card via ${api}: thousands of GPU compute units, one per pixel. Double precision like the CPU, yet individual pixels still differ (the graphics driver compiles the program in its own way); slow on gaming graphics cards.`); } },
  gpu_float:   { name: "GPU (float)", kind: L("Grafikkarte, einfache Genauigkeit", "graphics card, single precision"), short: "GPU float",
                 desc: L("Wie GPU (double), aber mit einfacher Genauigkeit: viel schneller, das Bild weicht leicht ab (in tiefen Zooms deutlich).",
                         "Like GPU (double), but with single precision: much faster, the image differs slightly (clearly in deep zooms).") },
};
const M = {
  job: -1, next: 0, polling: false, params: null, tiles: [], view: null,
  info: null, lastBenchKey: "",
};
const fmt = (v, d = 2) => v.toLocaleString(LANG, { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const workerColor = (w, a = 1) => `hsla(${(w * 137.508) % 360}, 75%, 55%, ${a})`;  // golden angle

listeners.push({ init: mInit, update: mUpdate });

function mInit(inf) {
  M.info = inf;
  const wk = $("m-workers");
  wk.max = inf.logical; wk.value = inf.logical; $("m-workers-l").textContent = inf.logical;
  wk.oninput = () => $("m-workers-l").textContent = wk.value;
  const names = L({ gesamt: "Gesamtansicht", seepferdchen: "Seepferdchental", spirale: "Spirale", elefanten: "Elefantental" },
                  { gesamt: "Full view", seepferdchen: "Seahorse Valley", spirale: "Spiral", elefanten: "Elephant Valley" });
  $("m-region").innerHTML = Object.keys(inf.regions).map((k) => `<option value="${k}">${names[k] || k}</option>`).join("");
  M.enames = Object.fromEntries(Object.entries(ENGINE_INFO).map(([k, v]) => [k, v.short]));
  // usable computation methods; unusable ones (e.g. no AVX2, no GPU) greyed out with the reason
  const label = (e) => ENGINE_INFO[e] ? `${ENGINE_INFO[e].name} (${ENGINE_INFO[e].kind})` : e;
  $("m-engine").innerHTML = inf.engines.map((e) => `<option value="${e}">${esc(label(e))}</option>`).join("") +
    Object.entries(inf.engines_off || {}).map(([e, r]) => `<option value="${e}" disabled>${esc(label(e))} – ${r}</option>`).join("");
  const showDesc = () => { const i = ENGINE_INFO[$("m-engine").value]; $("m-engine-desc").textContent = i ? i.desc : ""; };
  $("m-engine").addEventListener("change", showDesc);
  showDesc();
  // Overview of all computation methods (expandable)
  $("engine-table").innerHTML = `<table class="bt engines"><tr><th>${L("Rechenverfahren", "Computation method")}</th>` +
    `<th>${L("Art", "Kind")}</th><th>${L("Beschreibung", "Description")}</th><th>${L("hier", "here")}</th></tr>` +
    Object.entries(ENGINE_INFO).map(([e, i]) => `<tr><td><b>${esc(i.name)}</b></td><td>${esc(i.kind)}</td><td>${esc(i.desc)}</td>` +
      `<td>${inf.engines.includes(e) ? "✓" : `<span class="muted">${(inf.engines_off || {})[e] || "–"}</span>`}</td></tr>`).join("") + `</table>`;
  $("b-plan").textContent = inf.bench_workers.join(" · ");
  $("m-place").innerHTML = Object.entries(inf.placements).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  $("m-order").innerHTML = Object.entries(inf.orders).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  $("m-region").onchange = () => { M.view = null; };
  if (location.hash === "#zeit") $("b-view").value = "zeit";  // run-time view directly via link
  fetch("/api/mandel/status").then((r) => r.json()).then((s) => { renderScaling(s.bench); if (s.job > 0) poll(); });
}

// Resolution "long x short"; rotated, it becomes portrait
function size(sel) {
  const [a, b] = $(sel).value.split("x").map(Number);
  return $("m-rot").checked ? [b, a] : [a, b];
}

function baseParams() {
  const [w, h] = size("m-res");
  const p = { width: w, height: h, maxiter: +$("m-iter").value, tile: +$("m-tile").value,
              region: $("m-region").value, engine: $("m-engine").value, workers: +$("m-workers").value,
              rot90: $("m-rot").checked, placement: $("m-place").value, order: $("m-order").value,
              cardioid: $("m-card").checked };
  if (M.view) Object.assign(p, M.view);
  return p;
}

$("m-start").onclick = async () => {
  const r = await post("/api/mandel/start", baseParams());
  if (r.error) { $("m-status").textContent = r.error; return; }
  poll();
};
$("m-stop").onclick = () => post("/api/mandel/stop", {});
$("m-reset").onclick = () => { M.view = null; $("m-region").value = "gesamt"; $("m-start").click(); };
$("m-rot").onchange = () => { M.view = null; };
$("m-tint").onchange = () => $("m-tintcv").style.display = $("m-tint").checked ? "block" : "none";

// Zoom: click = 4× in, right-click = 4× out, each around the clicked point
function zoom(e, factor) {
  e.preventDefault();
  if (!M.params || M.running) return;
  const p = M.params, cv = $("m-img"), r = cv.getBoundingClientRect();
  const px = (e.clientX - r.left) / r.width * p.width, py = (e.clientY - r.top) / r.height * p.height;
  const scale = p.cw / p.width, dx = (px - p.width / 2) * scale, dy = (py - p.height / 2) * scale;
  M.view = p.rot90 ? { cx: p.cx + dy, cy: p.cy + dx, cw: p.cw / factor }   // rotated: right = +Im, down = +Re
                   : { cx: p.cx + dx, cy: p.cy - dy, cw: p.cw / factor };
  $("m-start").click();
}
$("m-wrap").onclick = (e) => zoom(e, 4);
$("m-wrap").oncontextmenu = (e) => zoom(e, 0.25);

// Fetch new tiles as long as a computation is running or tiles are still missing
async function poll() {
  if (M.polling) return;
  M.polling = true;
  try {
    for (;;) {
      const r = await (await fetch(`/api/mandel/tiles?job=${M.job}&since=${M.next}`)).json();
      heartbeat();
      const s = r.status;
      if (r.job !== M.job && s.params && !s.preparing) resetImage(r.job, s.params);
      if (r.job === M.job) {
        r.tiles.forEach(drawTile);
        M.next = r.next;
      }
      renderProgress(s);
      renderScaling(s.bench);
      const finished = !s.running && !s.bench.running && (r.job === M.job ? r.tiles.length === 0 : !s.params);
      if (finished) break;
      await new Promise((ok) => setTimeout(ok, r.tiles.length ? 30 : 150));
    }
  } finally { M.polling = false; }
}

function resetImage(job, p) {
  M.job = job; M.next = 0; M.params = p; M.tiles = [];
  for (const id of ["m-img", "m-tintcv"]) {
    const cv = $(id);
    cv.width = p.width; cv.height = p.height;
  }
  $("m-wrap").style.aspectRatio = `${p.width} / ${p.height}`;
  $("m-wrap").style.setProperty("--ar", p.width / p.height);
  const g = $("m-img").getContext("2d");
  g.fillStyle = "#0b0e14"; g.fillRect(0, 0, p.width, p.height);
  $("m-tintcv").getContext("2d").clearRect(0, 0, p.width, p.height);
}

function drawTile(t) {
  const bin = atob(t.data), img = new ImageData(t.w, t.h), d = img.data;
  for (let i = 0, j = 0; i < bin.length; i += 3, j += 4) {
    d[j] = bin.charCodeAt(i); d[j + 1] = bin.charCodeAt(i + 1); d[j + 2] = bin.charCodeAt(i + 2); d[j + 3] = 255;
  }
  $("m-img").getContext("2d").putImageData(img, t.x, t.y);
  const g = $("m-tintcv").getContext("2d");
  g.fillStyle = workerColor(t.worker, 0.45); g.fillRect(t.x, t.y, t.w, t.h);
  g.strokeStyle = "rgba(0,0,0,.35)"; g.lineWidth = 1; g.strokeRect(t.x + 0.5, t.y + 0.5, t.w - 1, t.h - 1);
  M.tiles.push({ worker: t.worker, ms: t.ms });
}

function mUpdate(m) {
  const s = m.mandel;
  M.running = s.running || s.bench.running;
  if (M.running && !M.polling) poll();
  if (!M.polling) { renderProgress(s); renderScaling(s.bench); }
}

function renderProgress(s) {
  const running = s.running || s.bench.running;
  $("m-start").disabled = running; $("b-start").disabled = running;
  setWorking($("m-status"), !!s.running);
  setWorking($("b-status"), !!s.bench.running);
  if (s.error) { $("m-status").textContent = L("Fehler: ", "Error: ") + s.error; return; }
  if (!s.params) return;
  const p = s.params;
  if (s.preparing) {
    $("m-status").textContent = isExt(p.engine)
      ? L(`bereite ${M.enames[p.engine]}-Programm vor (ggf. übersetzen) …`, `preparing the ${M.enames[p.engine]} program (compiling if needed) …`)
      : L(`starte ${p.workers} Worker-Prozesse …`, `starting ${p.workers} worker processes …`);
    return;
  }
  const pct = s.total ? s.done / s.total * 100 : 0;
  $("m-bar").style.width = pct + "%";
  const what = s.label || workersTxt(p.workers);
  const startup = s.startup > 0 ? ` · ${p.engine.startsWith("csharp") ? L(".NET-Start", ".NET startup") : L("Programmstart", "program startup")} ` +
    `${fmt(s.startup)} s ${L("(nicht mitgezählt)", "(not counted)")}` : "";
  const est = p.order === "teuer" && s.estimate_ms != null
    ? ` · ${L("Aufwandsschätzung", "effort estimate")} ${fmt(s.estimate_ms, 0)} ms ${L("(mitgezählt)", "(counted)")}` : "";
  const state = s.running ? L("läuft", "running") : s.stopped ? L("abgebrochen", "cancelled") : L("fertig", "done");
  $("m-status").innerHTML = `<b>${state}</b> · ${what} · ${s.done} / ${s.total} ${L("Kacheln", "tiles")} · ` +
    `<b>${fmt(s.elapsed || 0)} s</b> · ${p.width}×${p.height}, ${nf(p.maxiter)} ${L("Iter.", "iter.")}, ${M.enames[p.engine] || p.engine}` +
    (p.engine.startsWith("gpu")
      ? ` · ${s.device ? s.device.gpu : L("Grafikkarte", "graphics card")} (${s.device ? s.device.precision : ""}) · ` +
        L(`CPU färbt mit ${p.workers} Threads ein`, `CPU colors the image with ${p.workers} threads`)
      : ` · ${s.workers_seen || 0} ${isExt(p.engine) ? L("Threads", "threads") : L("Worker", "workers")} ${L("beteiligt", "involved")}`) +
    `${est}${startup}`;
  drawDist(p.workers);
}

// Bars: how many tiles each worker computed
function drawDist(nw) {
  const cv = $("m-dist"), dpr = devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (!w) return;
  cv.width = w * dpr; cv.height = h * dpr;
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const counts = new Array(nw).fill(0);
  M.tiles.forEach((t) => { if (t.worker < nw) counts[t.worker]++; });
  const max = Math.max(1, ...counts), bw = w / nw;
  counts.forEach((c, i) => {
    const bh = c / max * (h - 2);
    g.fillStyle = workerColor(i);
    g.fillRect(i * bw + 1, h - bh, Math.max(1, bw - 2), bh);
  });
}

// ---- Scaling test ----
$("b-start").onclick = async () => {
  const [w, h] = size("b-res");
  const p = { ...baseParams(), width: w, height: h, maxiter: +$("b-iter").value, repeats: +$("b-rep").value };
  delete p.workers;
  const r = await post("/api/mandel/bench", p);
  if (r.error) { $("b-status").textContent = r.error; return; }
  poll();
};
$("b-stop").onclick = () => post("/api/mandel/stop", {});
$("b-view").onchange = () => M.series && drawScaling(M.series);
$("b-cmp").onchange = () => { M.lastBenchKey = ""; fetch("/api/mandel/status").then((r) => r.json()).then((s) => renderScaling(s.bench)); };

function renderScaling(b) {
  if (!b) return;
  const key = JSON.stringify([b.running, b.current, b.results.length, b.file, b.error]);
  if (key === M.lastBenchKey) return;
  if (!M.resizeHooked) { M.resizeHooked = true; addEventListener("resize", () => M.series && drawScaling(M.series)); }
  M.lastBenchKey = key;
  const p = b.params;
  const desc = p ? `${p.width}×${p.height}, ${nf(+p.maxiter)} ${L("Iter.", "iter.")} · ${seriesName(p)}` +
    `${p.repeats > 1 ? L(` · Median aus ${p.repeats} Läufen`, ` · median of ${p.repeats} runs`) : ""}` : "";
  if (b.error) $("b-status").textContent = L("Fehler: ", "Error: ") + b.error;
  else if (b.running) $("b-status").innerHTML = `<b>${L("läuft", "running")}</b> · ${desc} · ` +
    L(`aktuell ${b.current ?? "–"} Worker (${b.results.length} / ${b.plan.length} fertig)`,
      `currently ${b.current ?? "–"} workers (${b.results.length} / ${b.plan.length} done)`);
  else if (b.results.length) $("b-status").innerHTML = `${desc}${b.file ? ` · ${L("gespeichert in", "saved in")} <code>benchmarks/${b.file}</code>` : ""}`;
  if (!b.results.length) { $("b-table").innerHTML = ""; $("b-chart").innerHTML = ""; return; }
  $("b-table").innerHTML = `<table class="bt"><tr><th>${L("Worker", "Workers")}</th><th>${L("Zeit", "Time")}</th>` +
    `<th>${L("Beschleunigung", "Speedup")}</th><th>${L("Effizienz", "Efficiency")}</th><th>${L("Prozessstart", "Process startup")}</th></tr>` +
    b.results.map((r) => `<tr><td>${r.workers}</td><td>${fmt(r.seconds)} s</td><td>${fmt(r.speedup, 1)} ×</td>` +
      `<td>${fmt(r.efficiency, 0)} %</td><td class="muted">${fmt(r.startup)} s</td></tr>`).join("") + `</table>`;
  buildSeries(b);
}

const isExt = (e) => /^(csharp|rust|c|cpp|asm|gpu)(_simd|_float)?$/.test(e);  // own program (threads or GPU)

// One chart series = computation method + placement + order. Color = language, dashed = SIMD.
const LANGS = ["numba", "csharp", "rust", "c", "cpp", "asm", "numpy", "gpu"];
const engineOf = (key) => key.split("|")[0];
const isSimd = (engine) => engine.endsWith("_simd") || engine === "asm" || engine === "gpu_float";  // dashed
const langColor = (engine) => `var(--s${LANGS.indexOf(engine.replace("_simd", "").replace("_float", "")) + 1})`;
const SERIES_COLORS = LANGS.flatMap((l) => [`${l}|windows|zeilen|0`, `${l}_simd|windows|zeilen|0`,
  `${l}|windows|zeilen|1`, `${l}_simd|windows|zeilen|1`]);  // sort order
const seriesKey = (p) => `${p.engine}|${p.placement || "windows"}|${p.order || "zeilen"}|${p.cardioid ? 1 : 0}`;
const PLACE_SHORT = { get windows() { return OS_LINUX() ? "Linux" : "Windows"; }, verteilt: L("1 Thread/Kern", "1 thread/core"), kompakt: L("kompakt", "compact") };
const seriesName = (p) => `${(M.enames && M.enames[p.engine]) || p.engine} · ${PLACE_SHORT[p.placement || "windows"]}` +
  ` · ${p.order === "teuer" ? L("aufwendige zuerst", "demanding first") : L("zeilenweise", "row by row")}` +
  `${p.cardioid ? L(" · Kardioide übersprungen", " · cardioid skipped") : ""}`;

// Comparison: per combination the newest saved run with the same image parameters (a running test replaces its own)
async function buildSeries(b) {
  const same = (q) => ["width", "height", "maxiter", "region", "tile"].every((k) => String(q[k]) === String(b.params[k]))
    && !!q.rot90 === !!b.params.rot90;
  let hist = [];
  try { hist = await (await fetch("/api/mandel/bench/history")).json(); } catch (e) { /* current run only */ }
  const byKey = {};
  hist.filter((h) => same(h.params) && h.results[0] && h.results[0].workers === 1)
    .forEach((h) => { byKey[seriesKey(h.params)] = { p: h.params, res: h.results }; });
  const current = seriesKey(b.params);
  byKey[current] = { p: b.params, res: b.results };
  const rank = (k) => (SERIES_COLORS.indexOf(k) + 1) || 99;
  // Comparison: languages directly (Windows, row by row), optionally without/with SIMD; the current run is always included
  const mode = $("b-cmp").value;
  // Default comparison: placement Windows, row by row, with the same cardioid setting as the current run
  const sameBasis = (k) => k.endsWith(`|windows|zeilen|${b.params.cardioid ? 1 : 0}`);
  const shown = (k) => k === current || mode === "alle" || (sameBasis(k) &&
    (mode === "beide" || (mode === "simd") === isSimd(engineOf(k))));
  M.series = Object.keys(byKey).filter((k) => byKey[k].res.length && shown(k)).sort((a, c) => rank(a) - rank(c))
    .map((k) => ({ key: k, name: seriesName(byKey[k].p), res: byKey[k].res }));
  drawScaling(M.series);
}

// Line chart: measured speedup per series vs. ideal (dashed), line at the number of physical cores
function drawScaling(series) {
  // PL = left padding (not "L", which is the global language function)
  const W = Math.max(320, $("b-chart").clientWidth || 560), H = Math.round(Math.min(360, W * 0.55)),
        PL = 44, R = 16, T = 16, B = 40;
  const all = series.flatMap((s) => s.res);
  const timeMode = $("b-view").value === "zeit";  // run time in s (log axis) instead of relative speedup
  const val = (r) => timeMode ? r.seconds : r.speedup;
  const maxW = Math.max(M.info.logical, ...all.map((r) => r.workers));
  const x = (v) => PL + v / maxW * (W - PL - R);
  let y, yt, tickLabel;
  if (timeMode) {
    const lo = Math.log10(Math.min(...all.map(val)) * 0.8), hi = Math.log10(Math.max(...all.map(val)) * 1.25);
    y = (v) => H - B - (Math.log10(v) - lo) / (hi - lo) * (H - T - B);
    yt = [0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50].filter((v) => Math.log10(v) >= lo && Math.log10(v) <= hi);
    tickLabel = (v) => `${fmt(v, v < 0.1 ? 2 : v < 1 ? 1 : 0)} s`;
  } else {
    const yMax = Math.ceil(Math.max(Math.max(...all.map(val)) * 1.15, 4) / 4) * 4;
    y = (v) => H - B - v / yMax * (H - T - B);
    yt = []; for (let v = 0; v <= yMax; v += yMax / 4) yt.push(v);
    tickLabel = (v) => `${v}×`;
    var ideal = `${x(1)},${y(1)} ${x(Math.min(maxW, yMax))},${y(Math.min(maxW, yMax))}`;
  }
  const tickStep = [1, 2, 4, 8, 16, 32, 64].find((s) => maxW / s <= 8) || 128;   // axis matching the thread count
  const xt = [1]; for (let v = tickStep; v <= maxW; v += tickStep) if (v > 1) xt.push(v);
  const phys = M.info.physical, showPhys = M.info.smt && phys < maxW;   // line only if there is SMT
  const col = (s) => langColor(engineOf(s.key));
  const dash = (s) => isSimd(engineOf(s.key)) ? "stroke-dasharray:7 4;" : "";
  const endLabel = (r) => timeMode ? `${fmt(r.seconds, r.seconds < 1 ? 3 : 2)} s` : `${fmt(r.speedup, 1)}×`;
  // Keep end labels from overlapping: sort by height and keep at least 14 px apart
  let ends = series.map((s) => ({ s, r: s.res[s.res.length - 1] })).sort((a, b) => y(val(a.r)) - y(val(b.r)));
  if (ends.length > 5) ends = [ends[0], ends[ends.length - 1]];  // many lines: label only the top and bottom one
  let prevY = -Infinity;
  ends.forEach((e) => { e.ly = Math.max(y(val(e.r)) - 10, prevY + 14); prevY = e.ly; });
  const aria = timeMode ? L("Laufzeit je Worker-Anzahl", "Run time by number of workers")
                        : L("Beschleunigung je Worker-Anzahl", "Speedup by number of workers");
  $("b-chart").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${aria}">
    ${yt.map((v) => `<line class="grid" x1="${PL}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>
      <text class="axis" x="${PL - 8}" y="${y(v) + 4}" text-anchor="end">${tickLabel(v)}</text>`).join("")}
    ${xt.map((v) => `<text class="axis" x="${x(v)}" y="${H - B + 18}" text-anchor="middle">${v}</text>`).join("")}
    <text class="axis" x="${(PL + W - R) / 2}" y="${H - 6}" text-anchor="middle">${L("Worker-Prozesse bzw. Threads", "Worker processes or threads")}</text>
    ${showPhys ? `<line class="ref" x1="${x(phys)}" x2="${x(phys)}" y1="${T}" y2="${H - B}"/>
    <text class="axis" x="${x(phys) + 6}" y="${timeMode ? T + 10 : H - B - 8}">${L(`${phys} physische Kerne`, `${phys} physical cores`)}</text>` : ""}
    ${timeMode ? "" : `<polyline class="ideal" points="${ideal}"/>`}
    ${series.map((s) => `<polyline class="meas" style="stroke:${col(s)};${dash(s)}"
        points="${s.res.map((r) => `${x(r.workers)},${y(val(r))}`).join(" ")}"/>`).join("")}
    ${series.map((s) => s.res.map((r) => `<circle class="pt" style="fill:${col(s)}" cx="${x(r.workers)}" cy="${y(val(r))}" r="4"/>
      <circle class="hit" cx="${x(r.workers)}" cy="${y(val(r))}" r="10"
        data-tip="${s.name} · ${workersTxt(r.workers)}: ${fmt(r.seconds, 3)} s · ${fmt(r.speedup, 1)}× · ${L("Effizienz", "efficiency")} ${fmt(r.efficiency, 0)} %"/>`).join("")).join("")}
    ${ends.map((e) => `<text class="lbl" x="${x(e.r.workers) - 8}" y="${e.ly}" text-anchor="end">${endLabel(e.r)}</text>`).join("")}
  </svg>
  <div class="legend chart-legend small">${series.map((s) => `<span><i class="sw" style="border-color:${col(s)};${
    isSimd(engineOf(s.key)) ? "border-top-style:dashed;" : ""}"></i>${s.name}</span>`).join("")}
    ${timeMode ? "" : `<span><i class="sw ideal"></i>ideal (linear)</span>`}</div>`;
  $("b-chart").querySelectorAll(".hit").forEach((c) => {
    c.onmouseenter = (e) => { const t = $("tip"); t.textContent = c.dataset.tip; t.style.display = "block"; };
    c.onmousemove = (e) => { const t = $("tip"); t.style.left = e.clientX + 12 + "px"; t.style.top = e.clientY - 28 + "px"; };
    c.onmouseleave = () => $("tip").style.display = "none";
  });
}
