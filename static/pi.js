// Pi: controls, phase display, result digits, scaling test with stacked bars per phase
const PI = { polling: false, lastKey: "" };
const PHASES = [
  { key: "reihe", name: L("Reihe (parallel)", "Series (parallel)"), col: "var(--s1)" },
  { key: "zusammenfuehren", name: L("Zusammenführen (nach oben hin seriell)", "Merging (increasingly serial towards the end)"), col: "var(--s3)" },
  { key: "abschluss", name: L("Wurzel + Division (seriell)", "Square root + division (serial)"), col: "var(--s4)" },
  { key: "umwandlung", name: L("Dezimalumwandlung (seriell)", "Decimal conversion (serial)"), col: "var(--s5)" },
  { key: "uebergabe", name: L("Übergabe zwischen Prozessen", "Transfer between processes"), col: "var(--muted)" },
];

listeners.push({ init: piInit, update: (m) => { if (m.pi.running || m.pi.bench.running) piPoll(); else if (!PI.polling) piRender(m.pi); } });

function piInit(inf) {
  const wk = $("pi-workers");
  wk.max = inf.logical; wk.value = inf.logical; $("pi-workers-l").textContent = inf.logical;
  wk.oninput = () => $("pi-workers-l").textContent = wk.value;
  $("pib-plan").textContent = inf.bench_workers.join(" · ");
  fetch("/api/pi/status").then((r) => r.json()).then(piRender);
}

$("pi-start").onclick = async () => {
  const r = await post("/api/pi/start", { digits: +$("pi-digits").value, workers: +$("pi-workers").value });
  if (r.error) { $("pi-status").textContent = r.error; return; }
  piPoll();
};
$("pi-stop").onclick = () => post("/api/pi/stop", {});
$("pib-start").onclick = async () => {
  const r = await post("/api/pi/bench", { digits: +$("pib-digits").value, repeats: +$("pib-rep").value });
  if (r.error) { $("pib-status").textContent = r.error; return; }
  piPoll();
};
$("pib-stop").onclick = () => post("/api/pi/stop", {});

async function piPoll() {
  if (PI.polling) return;
  PI.polling = true;
  try {
    for (;;) {
      const s = await (await fetch("/api/pi/status")).json();
      heartbeat();
      piRender(s);
      if (!s.running && !s.bench.running) break;
      await new Promise((ok) => setTimeout(ok, 250));
    }
  } finally { PI.polling = false; }
}

function piRender(s) {
  const busy = s.running || s.bench.running;
  $("pi-start").disabled = busy; $("pib-start").disabled = busy;
  setWorking($("pi-status"), !!s.running);
  setWorking($("pib-status"), !!s.bench.running);
  $("pi-dl").hidden = !s.download || busy;
  if (!s.have_gmpy) $("pi-status").textContent = L("Hinweis: gmpy2 fehlt – es wird mit Python-Zahlen gerechnet (deutlich langsamer).",
                                                   "Note: gmpy2 is missing – computing with Python numbers instead (much slower).");
  if (s.digits) {
    const pct = s.total ? s.done / s.total * 100 : 0;
    // Compare the language-neutral phase id (s.phase is display text in the server's language)
    const inSeries = s.phase_id ? s.phase_id === "series" : (s.total > 0 && s.done < s.total);
    $("pi-bar").style.width = (s.running ? (inSeries ? pct * 0.5 : 75) : 100) + "%";
    const what = s.label || workersTxt(s.workers);
    const start = s.startup > 0 ? ` · ${L("Prozessstart", "process startup")} ${fmt(s.startup)} s ${L("(nicht mitgezählt)", "(not counted)")}` : "";
    $("pi-status").innerHTML = s.error ? `${L("Fehler", "Error")}: ${s.error}` :
      `<b>${s.running ? s.phase : s.stopped ? L("abgebrochen", "cancelled") : L("fertig", "done")}</b> · ${what} · ` +
      `${nf(s.digits)} ${L("Stellen", "digits")} · ` +
      `${s.terms ? nf(s.terms) + L(" Reihenglieder · ", " series terms · ") : ""}<b>${fmt(s.elapsed || 0)} s</b>` +
      (s.check ? ` · ${s.check.ok ? "✓" : s.check.ok === false ? "✗" : ""} ${s.check.info}` : "") + start;
  }
  if (s.phases && s.phases.umwandlung != null) {
    $("pi-phases").innerHTML = phaseBar(s.phases, s.elapsed) + phaseLegend();
  }
  if (s.head && !s.running) {
    const head = s.head, tail = s.tail;
    $("pi-result").hidden = false;
    $("pi-result").innerHTML = `<div><span class="muted small">${L("Erste 100 Nachkommastellen", "First 100 decimal places")}</span>` +
      `<code>${head.slice(0, 2)}${group(head.slice(2))}</code></div>` +
      `<div><span class="muted small">${L(`Letzte 50 Stellen (bis Stelle ${nf(s.digits)})`, `Last 50 digits (up to digit ${nf(s.digits)})`)}</span>` +
      `<code>…${group(tail, s.digits % 10)}</code></div>`;
  }
  renderPiBench(s.bench);
}

// Digits in groups of ten; `offset` aligns the last digits with their real positions
function group(str, offset = 0) {
  const out = []; let i = 0;
  if (offset) { out.push(str.slice(0, offset)); i = offset; }
  for (; i < str.length; i += 10) out.push(str.slice(i, i + 10));
  return out.join(" ");
}

function phaseBar(ph, total) {
  const sum = PHASES.reduce((a, p) => a + (ph[p.key] || 0), 0) || 1;
  return `<div class="phasebar">${PHASES.map((p) => {
    const v = ph[p.key] || 0, w = v / sum * 100;
    return `<i style="width:${w}%;background:${p.col}" title="${p.name}: ${fmt(v, 3)} s (${fmt(w, 0)} %)">${w > 9 ? fmt(v, 2) + " s" : ""}</i>`;
  }).join("")}</div>`;
}
const phaseLegend = () => `<div class="legend chart-legend small">${PHASES.map((p) =>
  `<span><i class="swatch" style="background:${p.col}"></i>${p.name}</span>`).join("")}</div>`;

function renderPiBench(b) {
  if (!b) return;
  const key = JSON.stringify([b.running, b.current, b.results.length, b.file, b.error]);
  if (key === PI.lastKey) return;
  PI.lastKey = key;
  const p = b.params || {};
  const desc = p.digits ? `${nf(p.digits)} ${L("Stellen", "digits")}` +
    `${p.repeats > 1 ? L(` · Median aus ${p.repeats} Läufen`, ` · median of ${p.repeats} runs`) : ""}` : "";
  if (b.error) $("pib-status").textContent = L("Fehler: ", "Error: ") + b.error;
  else if (b.running) $("pib-status").innerHTML = `<b>${L("läuft", "running")}</b> · ${desc} · ` +
    L(`aktuell ${b.current ?? "–"} Worker (${b.results.length} / ${b.plan.length} fertig)`,
      `currently ${b.current ?? "–"} workers (${b.results.length} / ${b.plan.length} done)`);
  else if (b.results.length) $("pib-status").innerHTML = `${desc}${b.file ? ` · ${L("gespeichert in", "saved in")} <code>benchmarks/${b.file}</code>` : ""}`;
  if (!b.results.length) { $("pib-chart").innerHTML = ""; $("pib-table").innerHTML = ""; return; }
  const serial = (r) => r.phases.abschluss + r.phases.umwandlung;
  $("pib-table").innerHTML = `<table class="bt"><tr><th>${L("Worker", "Workers")}</th><th>${L("Zeit", "Time")}</th>` +
    `<th>${L("Beschleunigung", "Speedup")}</th><th>${L("davon seriell", "of which serial")}</th><th>${L("geprüft", "verified")}</th></tr>` +
    b.results.map((r) => `<tr><td>${r.workers}</td><td>${fmt(r.seconds)} s</td><td>${fmt(r.speedup, 1)} ×</td>` +
      `<td>${fmt(serial(r) / r.seconds * 100, 0)} %</td><td>${r.ok ? "✓" : r.ok === false ? "✗" : "–"}</td></tr>`).join("") + `</table>`;
  drawPiBench(b.results);
}

// Stacked bars: per worker count the time, split into the four phases; the speedup to the right
function drawPiBench(res) {
  // PL = left padding (not "L", which is the global language function)
  const W = Math.max(320, $("pib-chart").clientWidth || 560), rowH = 26, T = 8, PL = 70, R = 70, B = 30;
  const H = T + res.length * rowH + B;
  const max = Math.max(...res.map((r) => r.seconds));
  const x = (v) => PL + v / max * (W - PL - R);
  const ticks = []; const step = max > 20 ? 10 : max > 8 ? 2 : max > 3 ? 1 : 0.5;
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(v);
  $("pib-chart").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${L("Laufzeit je Phase und Worker-Zahl", "Run time by phase and number of workers")}">
    ${ticks.map((v) => `<line class="grid" x1="${x(v)}" x2="${x(v)}" y1="${T}" y2="${H - B}"/>
      <text class="axis" x="${x(v)}" y="${H - B + 16}" text-anchor="middle">${fmt(v, step < 1 ? 1 : 0)} s</text>`).join("")}
    ${res.map((r, i) => {
      const y = T + i * rowH + 4; let acc = 0;
      return `<text class="axis" x="${PL - 8}" y="${y + 13}" text-anchor="end">${workersTxt(r.workers)}</text>` +
        PHASES.map((p) => {
          const v = r.phases[p.key] || 0, x0 = x(acc); acc += v;
          return `<rect x="${x0}" y="${y}" width="${Math.max(0, x(acc) - x0 - 1)}" height="${rowH - 8}" rx="2" style="fill:${p.col}">
            <title>${workersTxt(r.workers)} · ${p.name}: ${fmt(v, 3)} s</title></rect>`;
        }).join("") +
        `<text class="lbl" x="${x(r.seconds) + 6}" y="${y + 13}">${fmt(r.speedup, 1)}×</text>`;
    }).join("")}
  </svg>${phaseLegend()}`;
}
