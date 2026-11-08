// Core Monitor frontend: WebSocket data -> tiles, sparklines, heatmap
const SPARK = 60;     // values per sparkline (60 s at 1 s interval)
const HIST = 120;     // heatmap columns (2 min)
const $ = (id) => document.getElementById(id);
const nf = (v) => Number(v).toLocaleString(LANG);   // number with the current language's grouping/decimal separators
const workersTxt = (n) => L(`${n} Worker`, n == 1 ? "1 worker" : `${n} workers`);

let n = 0, tiles = [], history = [], selected = new Set(), topo = [], info = null;
const listeners = [];   // further modules (mandel.js, pi.js) hook into the measurements here

// ---- Language: attributes that CSS cannot switch, language switch in the header, tell the server ----
if (LANG === "en") {
  document.querySelectorAll("[data-en-title]").forEach((el) => { el.title = el.dataset.enTitle; });
  document.querySelectorAll("[data-en-placeholder]").forEach((el) => { el.placeholder = el.dataset.enPlaceholder; });
  document.querySelectorAll("option[data-en]").forEach((o) => { o.textContent = o.dataset.en; });
}
// Server messages (errors, reasons, status labels) follow the server's language -> report ours first.
// Errors are ignored (e.g. an older server without /api/lang).
const langSent = fetch("/api/lang", { method: "POST", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify({ lang: LANG }) }).catch(() => {});
document.querySelectorAll(".lang-switch button").forEach((b) => {
  const on = b.dataset.lang === LANG;
  b.classList.toggle("on", on);
  b.setAttribute("aria-pressed", on ? "true" : "false");
  b.onclick = async () => {
    if (on) return;
    try { localStorage.setItem("km-lang-v2", b.dataset.lang); } catch (e) { /* storage blocked: still switch for now */ }
    try {
      await fetch("/api/lang", { method: "POST", headers: { "Content-Type": "application/json" },
                                 body: JSON.stringify({ lang: b.dataset.lang }) });
    } catch (e) { /* ignore */ }
    // Drop a ?lang= parameter, otherwise it would override the new choice
    const u = new URL(location.href);
    if (u.searchParams.has("lang")) { u.searchParams.delete("lang"); location.href = u.href; }
    else location.reload();
  };
});

// ---- Activity indicator: spinner on every running status line + a real sign of life ----
// The spinner alone would keep turning even if something hangs. So every server response
// (measurement tick every second, status polls) counts as a heartbeat; if it stops for > 5 s, the indicator turns red.
const STALE_AFTER = 5;
let lastBeat = Date.now();
const workStart = new Map();   // element -> start time (for lines without their own time from the server)
function heartbeat() { lastBeat = Date.now(); }
function setWorking(el, on) {
  if (on && !workStart.has(el)) workStart.set(el, Date.now());
  if (!on) workStart.delete(el);
  el.classList.toggle("working", on);
}
setInterval(() => {
  const age = (Date.now() - lastBeat) / 1000, stale = age > STALE_AFTER;
  document.body.classList.toggle("stale", stale);
  $("s-conn").classList.toggle("on", !stale && $("s-conn").dataset.ws === "1");
  if (!document.body.classList.contains("offline"))
    $("s-conn-l").textContent = stale ? L(`keine Rückmeldung seit ${Math.floor(age)} s`, `no response for ${Math.floor(age)} s`) : "Live";
  workStart.forEach((t0, el) => {   // run-time counter for lines that don't get one from the server
    const c = el.querySelector(".clock"), s = Math.floor((Date.now() - t0) / 1000);
    if (c) c.textContent = L(`läuft seit ${s} s`, `running for ${s} s`);
  });
}, 250);

// Color ramp 0..100 % -> RGB (dark, green, orange, red)
const STOPS = [[0, [30, 41, 59]], [35, [22, 163, 74]], [70, [217, 119, 6]], [100, [220, 38, 38]]];
function color(v) {
  for (let i = 1; i < STOPS.length; i++) {
    const [p1, c1] = STOPS[i], [p0, c0] = STOPS[i - 1];
    if (v <= p1) {
      const f = (v - p0) / (p1 - p0);
      return c0.map((c, k) => Math.round(c + (c1[k] - c) * f));
    }
  }
  return STOPS[STOPS.length - 1][1];
}
const css = (v) => `rgb(${color(v).join(",")})`;

async function init() {
  await langSent;   // so that the server's texts in /api/info (placements, orders, reasons) are in our language
  info = await (await fetch("/api/info")).json();
  n = info.logical;
  topo = info.topology;
  applySystem(info);
  const tpcN = Math.round(n / topo.length);
  $("topo-info").textContent = L(`${topo.length} Kerne × ${tpcN} Threads`, `${topo.length} cores × ${tpcN} threads`) +
    (info.l3.length ? L(`, ${info.l3.length} L3-Gruppen (CCX)`, `, ${info.l3.length} L3 groups (CCX)`) : "") +
    L(" · Zuordnung: ", " · Mapping: ") + info.topology_source;
  buildGrid();
  const heat = $("heat");
  heat.width = HIST; heat.height = n;
  heat.style.height = Math.max(n * 5, 120) + "px";
  heatLabels(Math.max(n * 5, 120));
  listeners.forEach((f) => f.init && f.init(info));
  connect();
}

// Put the detected hardware into the header, the system box and the texts (everything adapts to this computer)
function applySystem(inf) {
  const sys = inf.system, cpu = sys.cpu, isa = cpu.isa;
  const gpu = sys.gpus.find((g) => g.index === sys.gpu_default);
  const feats = ["avx", "avx2", "fma", "avx512f"].filter((k) => isa[k]).map((k) => k.toUpperCase()).join(", ") || L("kein AVX", "no AVX");
  const gpuText = gpu ? `${gpu.name} (${(gpu.vram_mb / 1024).toFixed(0)} GB${gpu.double ? "" : L(", ohne double", ", no double")})`
                      : L("keine nutzbare GPU", "no usable GPU");
  const coresThreads = L(`${cpu.physical} Kerne / ${cpu.logical} Threads`, `${cpu.physical} cores / ${cpu.logical} threads`);
  const summary = `${cpu.name}, ${coresThreads}, ${gpuText}`;
  $("sysinfo").textContent = `${sys.host} · ${cpu.name} · ${coresThreads} · ${gpuText}` +
    (cpu.simulated ? L(" · SIMULIERT", " · SIMULATED") : "");
  $("sys-short").textContent = summary + (cpu.simulated ? L(" (simuliert)", " (simulated)") : "");
  const off = Object.entries(sys.engines).filter(([, r]) => r);
  const row = (k, v) => `<div>${k}</div><div>${v}</div>`;
  $("sys-detail").innerHTML =
    row("CPU", `${cpu.name}${cpu.vendor ? ` (${cpu.vendor})` : ""}`) +
    row(L("Kerne / Threads", "Cores / threads"), `${cpu.physical} / ${cpu.logical}${cpu.smt
      ? L(` (SMT, ${cpu.threads_per_core} Threads je Kern)`, ` (SMT, ${cpu.threads_per_core} threads per core)`) : L(" (kein SMT)", " (no SMT)")}`) +
    row(L("Cache-Gruppen", "Cache groups"), cpu.l3_groups
      ? L(`${cpu.l3_groups} L3-Gruppen`, `${cpu.l3_groups} L3 groups`) +
        (cpu.l3_kb ? L(` à ${(cpu.l3_kb / 1024).toFixed(0)} MB`, ` of ${(cpu.l3_kb / 1024).toFixed(0)} MB each`) : "")
      : L("keine Angabe", "not reported")) +
    row(L("NUMA / Prozessorgruppen", "NUMA / processor groups"), `${cpu.numa_nodes} / ${cpu.processor_groups}${cpu.processor_groups > 1
      ? L(" (über 64 Threads: nur Platzierung „Windows“)", " (more than 64 threads: only placement “Windows”)") : ""}`) +
    row(L("Takt (max.)", "Clock (max.)"), cpu.max_mhz ? `${(cpu.max_mhz / 1000).toLocaleString(LANG, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHz` : "–") +
    row(L("Befehlssätze", "Instruction sets"), feats + (isa.avx2 ? "" : L(" – SIMD-Rechenverfahren nicht verfügbar", " – SIMD computation methods not available"))) +
    row(L("Arbeitsspeicher", "Memory (RAM)"), `${nf(cpu.ram_gb)} GB`) +
    row(L("Grafikkarten", "Graphics cards"), sys.gpus.length ? sys.gpus.map((g) => `${g.name}${g.software ? " (Software)" : ""}: ` +
      `${g.vram_mb ? (g.vram_mb / 1024).toFixed(0) + " GB, " : ""}${L("Feature-Level", "feature level")} ${g.feature_level}, ` +
      `double ${g.double ? L("ja", "yes") : L("nein", "no")}` +
      `${g.index === sys.gpu_default ? L(" <b>– wird verwendet</b>", " <b>– in use</b>") : ""}`).join("<br>") : L("keine gefunden", "none found")) +
    row(L("Skalierungsstufen", "Scaling steps"), sys.bench_steps.join(" · ")) +
    row(L("Nicht verfügbar", "Not available"), off.length ? off.map(([e, r]) =>
      `${typeof ENGINE_INFO !== "undefined" && ENGINE_INFO[e] ? ENGINE_INFO[e].name : e}: ${r}`).join("<br>") : "–") +
    row(L("Topologie-Quelle", "Topology source"), cpu.topology_source);
  // Placeholders in the texts
  const l3Threads = inf.l3.length ? inf.l3[0].length : 0, tpc = cpu.threads_per_core;
  const vals = { logical: cpu.logical, physical: cpu.physical, lastThread: cpu.logical - 1, summary,
                 l3Threads, l3Cores: Math.round(l3Threads / tpc),
                 tpcWord: (LANG === "en" ? { 2: "Two", 3: "Three", 4: "Four" } : { 2: "Zwei", 3: "Drei", 4: "Vier" })[tpc] || tpc };
  document.querySelectorAll("[data-sys]").forEach((el) => { if (vals[el.dataset.sys] != null) el.textContent = vals[el.dataset.sys]; });
  document.querySelectorAll("[data-if]").forEach((el) => {
    el.hidden = !({ smt: cpu.smt, l3: inf.l3.length > 0 }[el.dataset.if]);
  });
}

// Groups (CCX) -> cores -> threads; without L3 data 4 cores per group
function buildGrid() {
  const grid = $("grid");
  let groups = info.l3.map((lps) => topo.filter((c) => lps.includes(c[0])));
  if (!groups.length || groups.flat().length !== topo.length) {
    groups = [];
    for (let i = 0; i < topo.length; i += 4) groups.push(topo.slice(i, i + 4));
  }
  tiles = new Array(n);
  groups.forEach((cores, gi) => {
    const g = document.createElement("div");
    g.className = "ccx";
    g.innerHTML = `<div class="ccx-name">${info.l3.length ? "CCX" : L("Gruppe", "Group")} ${gi}</div><div class="ccx-cores"></div>`;
    cores.forEach((lps) => {
      const ci = topo.indexOf(lps);
      const c = document.createElement("div");
      c.className = "core";
      c.innerHTML = `<div class="core-name">${L("Kern", "Core")} ${ci}</div>`;
      lps.forEach((i) => {
        const el = document.createElement("div");
        el.className = "thread";
        el.title = L(`Logischer Prozessor ${i} (Kern ${ci})`, `Logical processor ${i} (core ${ci})`);
        el.innerHTML = `<span class="lp">${i}</span><canvas></canvas><span class="val">–</span>`;
        el.onclick = () => { selected.has(i) ? selected.delete(i) : selected.add(i); renderSel(); };
        c.appendChild(el);
        tiles[i] = { el, val: el.querySelector(".val"), cv: el.querySelector("canvas"), data: [] };
      });
      g.querySelector(".ccx-cores").appendChild(c);
    });
    grid.appendChild(g);
  });
}


function renderSel() {
  tiles.forEach((t, i) => t.el.classList.toggle("sel", selected.has(i)));
  $("l-cores").textContent = selected.size ? L(`${selected.size} gewählt`, `${selected.size} selected`) : L("alle", "all");
}
$("sel-all").onclick = (e) => { e.preventDefault(); selected = new Set([...Array(n).keys()]); renderSel(); };
$("sel-none").onclick = (e) => { e.preventDefault(); selected.clear(); renderSel(); };
$("sel-first").onclick = (e) => { e.preventDefault(); selected = new Set(topo.map((c) => c[0])); renderSel(); };

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => { $("s-conn").dataset.ws = "1"; document.body.classList.remove("offline"); heartbeat(); };
  ws.onclose = () => {
    $("s-conn").dataset.ws = "0";
    document.body.classList.add("offline");
    $("s-conn-l").textContent = L("Server nicht erreichbar – verbinde neu …", "Server unreachable – reconnecting …");
    setTimeout(connect, 1000);
  };
  ws.onmessage = (e) => {
    heartbeat();
    const m = JSON.parse(e.data);
    // New server start or changed page files -> reload right away. Same id (short network glitch): keep running.
    if (info && ((m.boot && m.boot !== info.boot) || (m.assets && info.assets && m.assets !== info.assets))) {
      $("s-conn-l").textContent = L("Server neu gestartet – lade neu …", "Server restarted – reloading …");
      location.reload();
      return;
    }
    update(m);
  };
}

function update(m) {
  $("s-total").textContent = m.total.toFixed(0) + " %";
  $("s-freq").textContent = m.freq ? (m.freq / 1000).toLocaleString(LANG, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " GHz" : "–";
  $("s-mem").textContent = m.mem.toFixed(0) + " %";
  $("s-mem-l").textContent = `RAM ${nf(m.mem_used)} / ${nf(m.mem_total)} GB`;

  m.cores.forEach((v, i) => {
    const t = tiles[i]; if (!t) return;
    t.data.push(v); if (t.data.length > SPARK) t.data.shift();
    t.val.textContent = v.toFixed(0) + " %";
    t.el.style.setProperty("--load", css(v));
    spark(t);
  });

  history.push(m.cores); if (history.length > HIST) history.shift();
  drawHeat();
  renderLoad(m.load);
  renderBench(m.bench);
  listeners.forEach((f) => f.update && f.update(m));
}

function spark(t) {
  const cv = t.cv, dpr = devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== w * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  const d = t.data, step = w / (SPARK - 1), x0 = w - (d.length - 1) * step;
  const last = d[d.length - 1] || 0;
  g.beginPath();
  d.forEach((v, k) => { const x = x0 + k * step, y = h - (v / 100) * (h - 2) - 1; k ? g.lineTo(x, y) : g.moveTo(x, y); });
  g.strokeStyle = css(last); g.lineWidth = 1.5; g.stroke();
  g.lineTo(x0 + (d.length - 1) * step, h); g.lineTo(x0, h); g.closePath();
  g.globalAlpha = 0.15; g.fillStyle = css(last); g.fill(); g.globalAlpha = 1;
}

// Labels on the left (CCX or groups with thread range) and separator lines between the groups
function heatLabels(h) {
  const groups = info.l3.length ? info.l3 : topo.reduce((acc, c, i) => {
    if (i % 4 === 0) acc.push([]);
    acc[acc.length - 1].push(...c);
    return acc;
  }, []);
  const row = h / n, rows = $("heat-rows"), lines = $("heat-lines");
  rows.style.height = h + "px"; lines.style.height = h + "px";
  groups.forEach((lps, gi) => {
    const lo = Math.min(...lps), hi = Math.max(...lps);
    const s = document.createElement("span");
    s.style.top = (lo + (hi - lo + 1) / 2) * row - 7 + "px";
    s.textContent = `${info.l3.length ? "CCX" : L("Gruppe", "Group")} ${gi} · T ${lo}–${hi}`;
    rows.appendChild(s);
    if (lo > 0) { const l = document.createElement("i"); l.style.top = lo * row + "px"; lines.appendChild(l); }
  });
}

function drawHeat() {
  const g = $("heat").getContext("2d");
  const img = g.createImageData(HIST, n);
  const off = HIST - history.length;
  history.forEach((row, x) => {
    row.forEach((v, y) => {
      const [r, gg, b] = color(v), p = (y * HIST + x + off) * 4;
      img.data[p] = r; img.data[p + 1] = gg; img.data[p + 2] = b; img.data[p + 3] = 255;
    });
  });
  g.putImageData(img, 0, 0);
}

// ---- Load generator ----
$("intensity").oninput = (e) => $("l-int").textContent = e.target.value + " %";
$("start").onclick = () => post("/api/load/start", {
  cores: selected.size ? [...selected] : null,
  intensity: $("intensity").value / 100,
  seconds: +$("seconds").value,
  pin: $("pin").checked,
});
$("stop").onclick = () => post("/api/load/stop", {});

function renderLoad(s) {
  setWorking($("load-status"), !!s.running);
  const k = s.cores ? s.cores.length : 0;
  $("load-status").textContent = s.running
    ? (s.starting ? L(`starte ${k} Prozesse … (${s.started || 0} gestartet)`, `starting ${k} processes … (${s.started || 0} started)`)
       : L(`aktiv: ${k} Prozesse, ${Math.round(s.intensity * 100)} %, ${s.pin ? "angepinnt" : "frei verteilt"}, noch ${s.remaining} s`,
           `active: ${k} processes, ${Math.round(s.intensity * 100)} %, ${s.pin ? "pinned" : "freely distributed"}, ${s.remaining} s left`))
    : L("keine Last aktiv", "no load active");
}

// ---- Benchmark ----
const BENCH_RUNNING = L("läuft … erst seriell, dann parallel", "running … first serial, then parallel") + ` · <span class="clock"></span>`;
$("bench").onclick = async () => {
  $("bench").disabled = true;
  $("bench-out").innerHTML = BENCH_RUNNING;
  setWorking($("bench-out"), true);
  const r = await post("/api/bench", { limit: +$("limit").value });
  $("bench").disabled = false;
  if (r.error) { setWorking($("bench-out"), false); $("bench-out").textContent = r.error; }
};

function renderBench(b) {
  if (b.running) {
    $("bench").disabled = true;
    if (!$("bench-out").classList.contains("working")) { $("bench-out").innerHTML = BENCH_RUNNING; setWorking($("bench-out"), true); }
    return;
  }
  setWorking($("bench-out"), false);
  $("bench").disabled = false;
  const r = b.result; if (!r) return;
  const f2 = (v) => v.toLocaleString(LANG, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  $("bench-out").innerHTML = `<table>
    <tr><td>${L("Primzahlen bis", "Primes up to")} ${nf(r.limit)}</td><td>${nf(r.primes)} ${r.ok ? "✓" : "✗"}</td></tr>
    <tr><td>${L("1 Prozess", "1 process")}</td><td>${f2(r.t_serial)} s</td></tr>
    <tr><td>${L(`${r.workers} Prozesse`, `${r.workers} processes`)}</td><td>${f2(r.t_parallel)} s</td></tr>
    <tr><td>${L(`Start der ${r.workers} Prozesse (nicht mitgezählt)`, `Startup of the ${r.workers} processes (not counted)`)}</td><td>${f2(r.t_startup)} s</td></tr>
    <tr><td>${L("Beschleunigung", "Speedup")}</td><td>${r.speedup.toLocaleString(LANG, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ×</td></tr>
    <tr><td>${L("Effizienz", "Efficiency")}</td><td>${r.efficiency} %</td></tr></table>`;
}

// Glossary: the search field hides non-matching entries (term and explanation are searched).
// One filter per language block: each .gloss-filter works on the .gloss-list / .gloss-none in its own wrapper.
document.querySelectorAll(".gloss-filter, #gloss-filter").forEach((inp) => {
  const box = inp.closest("[data-l]") || document.getElementById("gloss-box") || document;
  const list = box.querySelector(".gloss-list, #gloss-list"), none = box.querySelector(".gloss-none, #gloss-none");
  if (!list) return;
  inp.addEventListener("input", () => {
    const q = inp.value.trim().toLowerCase();
    let shown = 0;
    for (const dt of list.querySelectorAll("dt")) {
      const dd = dt.nextElementSibling;
      const hit = !q || (dt.textContent + " " + dd.textContent).toLowerCase().includes(q);
      dt.hidden = dd.hidden = !hit;
      shown += hit;
    }
    if (none) none.hidden = shown > 0;
  });
});

async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  heartbeat();
  return r.json();
}

init();
