[English](README.md) | Deutsch

# Kern-Monitor (Core Monitor) – Machbarkeitsstudie

Web-Oberfläche zum Überwachen und gezielten Auslasten aller CPU-Kerne – mit der
Mandelbrot-Menge als echter, parallel berechneter Aufgabe und einem Skalierungstest.

**Status:** Machbarkeitsstudie, experimentell. Läuft nur unter Windows 10/11 (64 Bit, x64).

## Start

    start.bat

oder manuell:

    python -m pip install -r requirements.txt
    python -m pip install numba        (optional, ca. 3–4× schnelleres Rechenverfahren)
    python server.py

Danach im Browser: http://127.0.0.1:8000 (start.bat öffnet die Seite selbst, falls sie nicht schon offen ist)

**Sprache:** Oben in der Kopfzeile schaltet **DE | EN** zwischen Deutsch und Englisch um. Die Wahl merkt sich der
Browser; ohne Wahl gilt die Sprache des Browsers. Meldungen des Servers folgen der gewählten Sprache. Die Startsprache
des Servers lässt sich mit `set KM_LANG=de` bzw. `set KM_LANG=en` festlegen (sonst gilt die Sprache der Windows-Oberfläche).

**Sicherheit:** Der Server bindet fest an `127.0.0.1` und ist damit nur auf diesem Rechner
erreichbar, nicht aus dem LAN oder Internet. Der Port lässt sich mit `set PORT=8001` ändern.

## Hinweis zum Virenscanner (unbegründete Warnungen)

Virenscanner (z. B. Microsoft Defender, Trend Micro) und Windows SmartScreen können bei diesem Programm Alarm schlagen
oder Teile blockieren – ein **Fehlalarm**, das Programm ist harmlos. Die Scanner urteilen nach Verhaltensmustern, und
der Kern-Monitor zeigt einige, die auch Schadprogramme haben:

- selbst übersetzte `.exe`-Dateien ohne digitale Signatur und ohne „Bekanntheit“ (C#, Rust, C, C++, Assembler, GPU),
- frisch entpackte, unbekannte Dateien aus einem ZIP,
- viele gleichzeitig gestartete Prozesse (bis zu 48 Python-Worker) und 100 % Auslastung aller Kerne (ähnlich wie ein Krypto-Miner).

**Anzeichen:** „Zugriff verweigert“ oder langsamer erster Start eines Rechenverfahrens; eine `.exe` landet in Quarantäne
(das Rechenverfahren erscheint ausgegraut mit „Programm fehlt – vermutlich von einem Virenscanner …“); SmartScreen-Warnung
„Der Computer wurde durch Windows geschützt“. Auf dem Referenzrechner beobachtet: direkt nach dem Entpacken scheiterten
einzelne Starts mit „Zugriff verweigert“, Sekunden später lief alles.

**Was tun:**

1. Ein paar Sekunden warten bzw. `start.bat` neu starten – der Monitor wiederholt einen gesperrten Start bis zu 10 s lang selbst.
2. Vor dem Entpacken: Rechtsklick auf die ZIP-Datei → Eigenschaften → „Zulassen“. SmartScreen: „Weitere Informationen“ → „Trotzdem ausführen“.
3. In der Quarantäne des Virenscanners nachsehen und die Datei wiederherstellen.
4. Den Ordner als Ausnahme eintragen – **nur bei vertrauenswürdiger Herkunft** (selbst gebaut oder direkt vom Ersteller).
5. Zur Kontrolle einzelne `.exe` bei [VirusTotal](https://www.virustotal.com) prüfen lassen oder das Paket „Lite“ (Klein) nehmen und selbst übersetzen.

Den Virenscanner bitte **nicht** abschalten. numba, numpy und Pi laufen auch, wenn alle `.exe`-Dateien blockiert sind.

## Weitergabe an andere PCs (Export)

| Paket | Bauen mit | Größe | Ziel-PC braucht |
|---|---|---|---|
| **„Full“ (Komplett)** | `export_full.bat` | ZIP ≈ 104 MB, entpackt ≈ 281 MB | nur Windows 10/11 (64 Bit) – kein Python, kein Internet, keine Admin-Rechte |
| **„Lite“ (Klein)** | `export_lite.bat` | ZIP ≈ 0,1 MB | Python 3.11+ und Internet beim ersten Start; optional .NET SDK, Rust, Visual Studio C++ (siehe INSTALLATION.de.txt) |

- Beide Batch-Dateien rufen `tools\export.ps1 -Variante Full` bzw. `-Variante Lite` auf.
- Ergebnis: `export\CoreMonitor_Full_<Datum>.zip` bzw. `export\CoreMonitor_Lite_<Datum>.zip`.
- Beide Pakete enthalten die Installationsanleitung auf Englisch (`INSTALLATION.txt`) und Deutsch (`INSTALLATION.de.txt`;
  Vorlagen in `tools\`: `INSTALLATION_Full.txt`, `INSTALLATION_Lite.txt`, `INSTALLATION_Komplett.txt`, `INSTALLATION_Klein.txt`),
  diese Beschreibung als `README.md` (Englisch) und `README.de.md` (Deutsch) sowie beide Projektberichte als PDF:
  `Project_Report_Core_Monitor.pdf` (Englisch) und `Projektbericht_Parallelisierung.pdf` (Deutsch).
- **Full** enthält eingebettetes Python 3.11.9 mit allen Paketen, alle Rechenverfahren fertig übersetzt (C/C++/Assembler/GPU mit
  statischer Laufzeitbibliothek, GPU-Shader vorübersetzt, `vcomp140.dll`; Rust statisch; C# als eigenständige .exe) und die
  Quelltexte. `start.bat` erkennt das eingebettete Python und installiert/übersetzt dann nichts.
- **Lite** enthält nur Quelltexte; `start.bat` installiert die Python-Pakete und übersetzt, was an Werkzeugen vorhanden ist.
  Fehlt ein Werkzeug, erscheinen die betroffenen Rechenverfahren ausgegraut mit Hinweis.
- **Datenschutz-Prüfung** (`tools\privacy_check.py`, läuft bei jedem Export automatisch): Alle Dateien des Pakets –
  Text und Binärdateien (ASCII und UTF-16) sowie der Text der PDFs – werden nach Angaben über den bauenden PC durchsucht:
  Benutzerprofil/-name, Projektpfad, Rechnername, LAN-Adressen, MAC-Adressen, OneDrive-Pfad. Die Muster werden zur
  Laufzeit ermittelt; bei einem Treffer wird kein ZIP erzeugt. Dafür: C# ohne Debug-Informationen und mit neutralen
  Pfaden (`MandelBench.csproj`), pip-Startprogramme (`site-packages\bin`, enthalten den Python-Pfad des PCs) entfallen,
  `__pycache__` entfällt, C/C++/Assembler/Rust enthalten keine Debug-Pfade.
- Eigene Messdaten (`benchmarks\`), lokale Werkzeug-Einstellungen, Protokolle und Zwischendateien kommen nicht mit; die
  mpmath-Referenz für Pi ist im Paket „Full“ enthalten (im Paket „Lite“ wird sie beim ersten Pi-Lauf erzeugt).
- Fehlen beim Start die Werkzeuge, verwendet der Server die mitgelieferten Programme; neu übersetzt wird nur, wenn ein
  Quelltext deutlich (> 1 Minute) neuer ist und die Werkzeuge vorhanden sind.
- Getestet: beide Pakete in fremden Ordnern; „Full“ mit leerem PATH (alle 13 Rechenverfahren, Pi, Skalierungstest) und
  mit simuliertem kleinem PC; „Lite“ mit allen Werkzeugen (alles übersetzt, 13 Rechenverfahren) und nur mit Python.

## Hardware-Erkennung

Beim Start erkennt `hardware.py` den Rechner, alles andere richtet sich danach. So läuft das Programm auch auf
anderen PCs.
- **CPU:** Name, Hersteller, Kerne und Threads, SMT, Kern-/Thread-Zuordnung, L3-Gruppen (CCX), NUMA-Knoten,
  Prozessorgruppen, Takt, Befehlssätze (SSE2, AVX, AVX2, FMA, AVX-512F), Arbeitsspeicher
- **Grafikkarten:** alle über DXGI (`native/bin/mandel_gpu.exe --probe`) mit Name, Speicher, Treiber, Feature-Level,
  Compute-Shader und double. Verwendet wird automatisch die Karte mit dem meisten eigenen Speicher (keine Software-Karte).
- **Daraus abgeleitet:** Worker-/Thread-Regler (Maximum und Voreinstellung = Zahl der Threads), Stufen der
  Skalierungstests (Zweierpotenzen, halbe/ganze Kernzahl, Mitte des SMT-Bereichs, alle Threads), Kernansicht und
  Heatmap (nach L3-Gruppen und SMT, sonst einfache Gruppen), Platzierungen („kompakt“ nur mit SMT; über 64 Threads nur
  „Windows“), angebotene Rechenverfahren (SIMD und Assembler nur mit AVX2, GPU nur mit Direct3D-11-Compute, „GPU double“
  nur mit double-Unterstützung; nicht nutzbare erscheinen ausgegraut mit Begründung), Diagrammachsen und die Zahlen in
  den Erklärtexten. Messwerte in den Erklärungen sind als Werte des Referenzrechners gekennzeichnet.
- C, C++ und Assembler werden **ohne** `/arch:AVX2` übersetzt und prüfen zur Laufzeit, ob AVX2 vorhanden ist; sie laufen
  damit auch auf älteren CPUs (gleiches Bild, gleiche Geschwindigkeit wie vorher gemessen).
- Die erkannten Werte zeigt die Box „System“ oben auf der Seite und `GET /api/system`.
- Test eines anderen Rechners: `set KM_SIMULATE=logical=8,physical=8,avx2=0,fma=0,gpu=0` vor dem Start.

## Funktionen

- **Auslastung pro Kern**: alle 48 Threads, gruppiert nach den 24 physischen Kernen
  (je 2 SMT-Threads) und den 8 L3-Gruppen (CCX, je 3 Kerne). Aktualisierung jede Sekunde
  per WebSocket, mit 60-s-Verlauf je Thread. Dazu CPU gesamt, Takt und RAM.
  Die Zuordnung Kern ↔ Thread kommt unter Windows aus `GetLogicalProcessorInformationEx`
  (per ctypes), sonst gilt die Annahme „Thread 2n und 2n+1 = Kern n“.
- **Mandelbrot-Menge** (neben der Kernansicht, damit die Lastverteilung sichtbar ist):
  - das Bild wird in Kacheln zerlegt, ein Prozess-Pool (`ProcessPoolExecutor`) mit 1–48 Workern berechnet sie
  - Rechenverfahren (13, siehe Tabelle unten): Python + numba (JIT-kompiliert), Python + numpy (vektorisiert), C# / .NET mit echten Threads
    oder C# + SIMD (AVX2, 4 Pixel je Thread)
    (nur wenn das .NET SDK installiert ist; start.bat übersetzt das C#-Programm, sonst geschieht das beim ersten Aufruf)
  - Reihenfolge der Kacheln: zeilenweise oder „aufwendige Kacheln zuerst“ (grobe Aufwandsschätzung vorab, die Zeit dafür wird mitgemessen)
  - Auflösung, max. Iterationen, Ausschnitt und Kachelgröße wählbar; Start/Stopp; Fortschritt und Zeit
  - Kacheln erscheinen live, sobald sie fertig sind; optional nach Worker eingefärbt,
    darunter ein Balken je Worker mit der Zahl seiner Kacheln
  - Darstellung standardmäßig um 90° im Uhrzeigersinn gedreht (Hochformat, reelle Achse senkrecht,
    Spitze oben); abschaltbar mit „um 90° gedreht“. Die Auflösung gilt dann als Hochformat (z. B. 1200 × 1920).
  - Klick ins Bild zoomt 4× hinein, Rechtsklick heraus
  - Der Pool bleibt nach einer Berechnung bestehen; der Prozessstart wird getrennt gemessen und nicht mitgezählt
  - Platzierung der Worker: „Windows entscheidet“, „1 Thread je Kern zuerst“ (über alle CCX verteilt) oder
    „kompakt“ (beide Threads eines Kerns, CCX für CCX), umgesetzt über CPU-Affinität je Worker-Prozess
- **Skalierungstest**: dasselbe Bild nacheinander mit 1, 2, 4, 8, 12, 16, 24, 32 und 48 Workern;
  wahlweise 1, 3 oder 5 Läufe je Stufe (Median). Tabelle und Diagramm (Beschleunigung gemessen vs. ideal,
  eine Linie je Platzierung zum Vergleich). Ergebnisse werden gespeichert in
  `benchmarks/mandelbrot_<Zeitstempel>.json` und fortlaufend in `benchmarks/mandelbrot_benchmarks.csv`
  (Semikolon, Dezimalkomma – direkt in Excel lesbar).
- **Pi berechnen**: 1 000 bis 100 Millionen Nachkommastellen, Chudnovsky-Formel mit Binary Splitting, große Zahlen
  mit GMP (`gmpy2`). Die Reihe wird in einen Block je Worker zerlegt (parallel), dann paarweise zusammengeführt
  (nach oben hin immer weniger parallel), zum Schluss Wurzel, Division und Dezimalumwandlung (seriell). Die vier
  Phasen werden getrennt gemessen und als Balken angezeigt. Erste 100 und letzte 50 Stellen auf der Seite, alle
  Stellen als Download (`benchmarks/pi_ergebnis.txt`). Prüfung gegen *mpmath* (unabhängige Implementierung,
  bis 1 Mio. Stellen; Referenz in `benchmarks/pi_referenz_mpmath.txt`). Skalierungstest mit Phasenaufteilung,
  Ergebnisse in `benchmarks/pi_<Zeitstempel>.json` und `benchmarks/pi_benchmarks.csv`.
- **Arbeitsanzeige**: Jede laufende Berechnung (Mandelbrot, beide Skalierungstests, Pi, Last-Generator,
  Primzahl-Benchmark) zeigt einen drehenden Kreisel mit aktueller Phase und Zeit. Zusätzlich gibt es ein echtes
  Lebenszeichen: Bleiben Daten vom Server länger als 5 s aus, wird die Anzeige rot („keine Rückmeldung seit … s“).
  Bei „Bewegung reduzieren“ im Betriebssystem steht der Kreisel still.
- **Automatisches Neuladen**: Der Server schickt eine Startkennung und einen Fingerabdruck der Seitendateien mit.
  Startet der Server neu oder ändert sich eine Datei in `static/`, lädt sich jede offene Seite sofort selbst neu
  (gemessen: nach 0,7–0,8 s). Bei einer kurzen Verbindungsstörung mit unveränderter Kennung wird nicht neu geladen,
  laufende Anzeigen bleiben erhalten.
- **Kein zusätzlicher Browser-Tab**: start.bat öffnet keinen Tab mehr fest. Der Server wartet nach dem Start 3,5 s;
  hat sich bis dahin eine offene Seite neu verbunden, lädt nur sie neu. Ist keine Seite offen, öffnet er genau einen
  Tab (gesteuert über `OPEN_BROWSER=1`, das start.bat setzt; bei `python server.py` von Hand wird nichts geöffnet).
- **Zweisprachig (DE | EN)**: Umschaltung in der Kopfzeile, Wahl im Browser gespeichert, Voreinstellung = Browsersprache;
  Servermeldungen in der gewählten Sprache (`POST /api/lang`), Startsprache über `KM_LANG=de|en`.
- **Heatmap** aller Threads über die letzten 2 Minuten
- **Last-Generator**: ein Prozess pro Thread, Intensität 5–100 %, Dauer wählbar,
  optional fest an den Thread gebunden (CPU-Affinität). Threads per Klick auswählbar.
- **Primzahl-Benchmark**: seriell vs. verteilt auf alle Kerne

## Die 13 Rechenverfahren (Mandelbrot)

| Rechenverfahren | Art | Beschreibung |
|---|---|---|
| Python + numba | Prozesse, 1 Pixel je Schritt | Python, von numba in Maschinencode übersetzt; wegen des GIL ein Prozess je Kern |
| Python + numpy | Prozesse, Feldrechnung | reines Python mit numpy, rechnet ganze Kacheln als Zahlenfelder; langsamste Variante |
| C# / .NET | Threads, 1 Pixel je Schritt | C# (.NET 10) mit echten Threads in einem Prozess |
| C# / .NET + SIMD | Threads, 4 Pixel gleichzeitig | wie C#, je Thread 4 Bildpunkte gleichzeitig (AVX2, `Vector256<double>`) |
| Rust | Threads, 1 Pixel je Schritt | Rust mit echten Threads und gemeinsamer Kachel-Warteschlange |
| Rust + SIMD | Threads, 4 Pixel gleichzeitig | Rust mit AVX2-Befehlen |
| C | Threads, 1 Pixel je Schritt | C mit Windows-Threads (`CreateThread`) |
| C + SIMD | Threads, 4 Pixel gleichzeitig | C mit AVX2-Intrinsics |
| C++ | Threads, 1 Pixel je Schritt | C++ mit `std::thread` und `std::atomic` |
| C++ + SIMD | Threads, 4 Pixel gleichzeitig | C++ mit AVX2-Intrinsics |
| Assembler | Threads, 4 Pixel gleichzeitig | handgeschriebener x64-Assembler (AVX2) für die innere Schleife, Threads in C |
| GPU (double) | Grafikkarte, doppelte Genauigkeit | Direct3D-Compute-Shader, je Bildpunkt eine GPU-Recheneinheit; doppelte Genauigkeit wie die CPU, wenige Pixel weichen trotzdem ab (Treiber) |
| GPU (float) | Grafikkarte, einfache Genauigkeit | wie GPU (double), viel schneller, Bild weicht leicht ab |

Interne Kennungen (API, Messdateien): `numba`, `numpy`, `csharp`, `csharp_simd`, `rust`, `rust_simd`, `c`, `c_simd`,
`cpp`, `cpp_simd`, `asm`, `gpu`, `gpu_float`. Die Reihenfolge „aufwendige Kacheln zuerst“ heißt intern `teuer` und in
CSV/JSON `aufwendige_zuerst`.

## Aufbau

| Datei | Inhalt |
|---|---|
| `hardware.py` | Hardware-Erkennung (CPU, Topologie, Befehlssätze, Grafikkarten), Skalierungsstufen, Simulation für Tests |
| `server.py` | kleine Startdatei (setzt Umgebung, startet `app.py`) – bewusst winzig, weil Worker-Prozesse sie neu laden |
| `app.py` | FastAPI-Backend: Messung (psutil), WebSocket, Hardware-Anbindung, Last-Generator, Primzahl-Benchmark, API |
| `worker_util.py`, `lastgen.py` | leichte Module für Worker- und Last-Prozesse (kein Webserver, kein numba im Worker) |
| `tools/export.ps1`, `export_full.bat`, `export_lite.bat` | Weitergabe-Pakete bauen (`-Variante Full` bzw. `Lite`, siehe „Weitergabe“) |
| `tools/glossar.py` | Begriffsliste – einzige Quelle für „Begriffe kurz erklärt“ in README.de.md, „Glossary“ in README.md, Webseite und Bericht (`python tools\glossar.py` erzeugt neu, `… check` prüft die Links) |
| `mandelbrot.py` | Mandelbrot-Rechenverfahren (numba/numpy), Einfärbung, Prozess-Pool, Skalierungstest, CSV/JSON |
| `static/index.html`, `app.js`, `style.css` | Oberfläche und Kernansicht, ohne externe Bibliotheken |
| `static/mandel.js` | Mandelbrot-Steuerung, Live-Kacheln, Skalierungsdiagramm (SVG) |
| `pi.py` | Pi-Berechnung (Chudnovsky, Binary Splitting, gmpy2), Prozess-Pool, Phasenmessung, Prüfung, Skalierungstest |
| `static/pi.js` | Pi-Steuerung, Phasenbalken, Stellen-Anzeige, Skalierungsdiagramm |
| `native/` | C (`c/mandel.c`), C++ (`cpp/mandel.cpp`), Assembler (`asm/kernel.asm`), GPU (`gpu/mandel.hlsl`, `gpu/mandel_gpu.cpp`), gemeinsamer Kern `mandel_core.h`, `build.bat` |
| `rust/mandelbench/` | Rust-Gegenstück (echte Threads, skalar und AVX2-SIMD), gleiches Protokoll wie C#; Rechenverfahren „Rust“ und „Rust SIMD“ |
| `csharp/MandelBench/` | C#-Gegenstück (.NET 10, echte Threads): gleiche Kacheln, Formel und Farben; vom Server als Rechenverfahren „C#“ gestartet |
| `benchmarks/` | gespeicherte Ergebnisse des Skalierungstests |

## API

- `GET /api/info` – CPU-Daten, Topologie (`topology`, `l3`), verfügbare Rechenverfahren, aktuelle Sprache (`lang`)
- `POST /api/lang` – `{"lang":"de"}` oder `{"lang":"en"}`: Sprache der Servermeldungen
- `POST /api/mandel/start` – `{"workers":48, "width":1200, "height":1920, "maxiter":1000, "tile":128, "region":"gesamt", "engine":"numba", "rot90":true}`
  (optional `cx`, `cy`, `cw` für einen eigenen Ausschnitt)
- `POST /api/mandel/stop`
- `GET /api/mandel/status`
- `GET /api/mandel/tiles?job=1&since=0` – fertige Kacheln (RGB, base64)
- `POST /api/mandel/bench` – wie `start`, ohne `workers`; optional `worker_list`, `repeats` (Median)
- `GET /api/mandel/bench/history` – alle gespeicherten Skalierungstests
- Parameter `placement` (bei `start` und `bench`): `windows` | `verteilt` | `kompakt`;
  `order`: `zeilen` | `teuer`; `engine`: `numba` | `numpy` | `csharp` | `csharp_simd` | `rust` | `rust_simd` | `c` | `c_simd` | `cpp` | `cpp_simd` | `asm` | `gpu` | `gpu_float`; `cardioid`: `true` | `false`
- `POST /api/pi/start` – `{"digits":1000000, "workers":48}`; `POST /api/pi/stop`; `GET /api/pi/status`
- `POST /api/pi/bench` – `{"digits":10000000, "repeats":3}` (optional `worker_list`); `GET /api/pi/download` – alle Stellen als .txt
- `POST /api/load/start` – `{"cores":[0,1], "intensity":0.8, "seconds":30, "pin":true}` (`cores` weglassen = alle)
- `POST /api/load/stop`
- `POST /api/bench` – `{"limit":3000000}` (Primzahlen)
- `WS /ws` – Messwerte jede Sekunde

## Erkenntnisse (Threadripper 3960X, 24 Kerne / 48 Threads)

- Python nutzt mehrere Kerne nur über **mehrere Prozesse** (wegen des GIL), nicht über Threads.
- Unter Windows dauert das Starten der Prozesse spürbar (48 Worker mit numba: ca. 2–8 s).
  Deshalb bleibt der Pool bestehen und der Start wird getrennt ausgewiesen.
- Primzahlen bis 3 Mio.: 7,0 s seriell, 0,7 s parallel, also etwa 10× schneller.
- **Mandelbrot-Skalierungstest** (2560 × 1600, 5000 Iterationen, Gesamtansicht, numba, 128-px-Kacheln):

  | Worker | 1 | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 |
  |---|---|---|---|---|---|---|---|---|---|
  | Zeit (s) | 10,41 | 5,43 | 2,78 | 1,42 | 1,00 | 0,81 | 0,63 | 0,53 | 0,43 |
  | Beschleunigung | 1,0 | 1,9 | 3,8 | 7,4 | 10,4 | 12,9 | 16,4 | 19,5 | 24,5 |

  Bis 8 Worker fast linear, danach flacht die Kurve ab. Die erste Vermutung („SMT-Threads bringen wenig“) hat sich
  bei der Messung mit Platzierung **nicht** bestätigt, siehe unten: Hauptursache ist die kurze Laufzeit bei vielen Workern.
- numba ist für diese Aufgabe etwa 3–4× schneller als vektorisiertes numpy.
- **Rust-Vergleich** (08.11.2026, gleiche Parameter: 1600 × 2560 gedreht, 5000 Iterationen, zeilenweise,
  Platzierung „Windows“, Median aus 3; Zeit in s, Beschleunigung):

  | Worker/Threads | numba | C# | Rust | C# SIMD | Rust SIMD |
  |---|---|---|---|---|---|
  | 1 | 6,18 (1,0×) | 6,09 (1,0×) | 6,21 (1,0×) | 1,65 (1,0×) | 1,63 (1,0×) |
  | 8 | 0,93 (6,6×) | 0,83 (7,3×) | 0,85 (7,3×) | 0,23 (7,3×) | 0,22 (7,5×) |
  | 24 | 0,51 (12,1×) | 0,40 (15,4×) | 0,40 (15,6×) | 0,11 (15,0×) | 0,10 (15,8×) |
  | 48 | 0,34 (18,4×) | 0,23 (26,9×) | 0,22 (27,8×) | 0,070 (23,6×) | **0,062 (26,3×)** |
  | Start | 1,7–5,8 s (Pool) | 0,14 s | 0,04 s | 0,14 s | 0,04 s |

  - Rust (`rust/mandelbench`, ohne externe Pakete) nutzt dasselbe Protokoll wie C#: gleiche Kacheln, Formel und Farben,
    echte Threads mit gemeinsamer Kachel-Warteschlange, optionale Affinität, SIMD mit AVX2-Intrinsics ohne FMA.
    **Bitgenau dasselbe Bild** wie numba und C# (geprüft, auch mit Restspalten).
  - Rust und C# sind gleich schnell: Beide erzeugen nahezu denselben Maschinencode. Rust startet schneller und war mit
    48 SIMD-Threads gut 10 % vorn. Entscheidend sind echte Threads (gegenüber Python-Prozessen) und SIMD, nicht die Sprache.
  - Rust ist benutzerlokal über rustup installiert (`%USERPROFILE%\.cargo`, ohne PATH-Änderung); start.bat und der
    Server finden cargo auch dort. Ohne Rust fehlen die beiden Einträge einfach in der Auswahl.
  - Pi in Rust wurde nicht gebaut: Schnelle Langzahl-Bibliotheken für Rust (`rug`) setzen GMP voraus, das sich unter
    Windows/MSVC nur mühsam übersetzen lässt; reine Rust-Bibliotheken (`num-bigint`) sind bei Millionen Stellen um ein
    Vielfaches langsamer. Der Vergleich würde dann die Bibliothek messen, nicht die Parallelisierung.
- **C, C++ und Assembler** (08.11.2026, Visual Studio 2026 / MSVC 14.51, `/O2 /arch:AVX2 /fp:precise`, gleiche Parameter,
  zeilenweise, Platzierung „Windows“, Median aus 3; Zeit in s):

  | Threads | numba | C# | Rust | C | C++ | C# SIMD | Rust SIMD | C SIMD | C++ SIMD | Assembler (AVX2) |
  |---|---|---|---|---|---|---|---|---|---|---|
  | 1 | 6,18 | 6,09 | 6,21 | 6,08 | 6,06 | 1,65 | 1,63 | 1,66 | 1,67 | 1,69 |
  | 8 | 0,93 | 0,83 | 0,85 | 0,81 | 0,80 | 0,23 | 0,22 | 0,22 | 0,23 | 0,23 |
  | 24 | 0,51 | 0,40 | 0,40 | 0,39 | 0,39 | 0,11 | 0,10 | 0,11 | 0,11 | 0,11 |
  | 48 | 0,34 | 0,23 | 0,22 | 0,23 | 0,24 | 0,070 | 0,062 | 0,070 | 0,071 | 0,072 |
  | Start | 1,7–5,8 | 0,14 | 0,04 | 0,10 | 0,10 | 0,14 | 0,04 | 0,10 | 0,10 | 0,10 |

  - `native/`: C mit Win32-Threads (`CreateThread`, `InterlockedIncrement`), C++ mit `std::thread`/`std::atomic`,
    gemeinsamer Rechenteil `mandel_core.h` (skalar und AVX2-Intrinsics), handgeschriebener MASM-Kern
    `asm/kernel.asm` (AVX2, 4 Pixel in ymm-Registern, ohne FMA, ausführlich kommentiert) mit C-Rahmenprogramm.
    `native/build.bat` sucht Visual Studio über vswhere; start.bat ruft es auf und überspringt es ohne Visual Studio.
  - Alle fünf liefern **bitgenau dasselbe Bild** (0 Pixel Unterschied). Dafür nötig: `/fp:precise` (kein FMA) und
    `#pragma loop(no_vector)` an der Farbberechnung, damit der Compiler nicht auf Vektor-Mathefunktionen ausweicht.
  - **Ergebnis:** Alle kompilierten Sprachen liegen innerhalb weniger Prozent, der Assembler-Kern ist nicht schneller
    als der Compiler. Die Schleife ist durch die Wartezeit zwischen abhängigen Rechenschritten begrenzt, nicht durch die
    Sprache. Was wirklich zählt: SIMD (≈ 3,7×) und echte Threads statt Prozesse.
- **Klügerer Algorithmus: Kardioide/Kreis überspringen** (Option in allen Rechenverfahren, auch SIMD und Assembler;
  bei 4 Pixeln gleichzeitig starten Punkte in der Kardioide als „fertig“). Formel: q = (x − ¼)² + y², in der Menge
  wenn q·(q + x − ¼) ≤ y²/4 oder (x + 1)² + y² ≤ 1/16. Das Bild bleibt **exakt gleich** (0 Pixel Unterschied in allen
  11 CPU-Rechenverfahren, geprüft in Gesamtansicht und direkt an den Rändern von Kardioide und Kreis).
  Messung Rust bzw. Rust SIMD (1600 × 2560, 5000 It.; Zeit ohne → mit Test):

  | Ansicht | Rust, 1 Thread | Rust, 48 Threads | Rust SIMD, 1 Thread | Rust SIMD, 48 Threads |
  |---|---|---|---|---|
  | Gesamtansicht | 6,38 → 0,73 s (8,7×) | 0,24 → 0,11 s (2,3×) | 1,67 → 0,29 s (5,7×) | 0,068 → 0,032 s (2,1×) |
  | Rand der Kardioide | 27,7 → 2,0 s (13,6×) | 0,80 → 0,21 s (3,7×) | 6,9 → 0,64 s (10,8×) | 0,21 → 0,053 s (3,9×) |
  | Seepferdchental | 1,76 → 1,77 s (1,0×) | 0,13 → 0,13 s | 0,73 → 0,73 s | 0,040 → 0,039 s |

  Ein besserer Algorithmus schlägt mehr Kerne: 1 Thread mit Test ist schneller als 8 Threads ohne. Mit 48 Threads ist
  der Gewinn kleiner, weil die verbleibende Arbeit ungleich verteilt und die Laufzeit nur noch Hundertstelsekunden ist.
- **GPU** (NVIDIA GeForce RTX 3090, Treiber 610.88): Direct3D-11-Compute-Shader `native/gpu/mandel.hlsl`, zur Laufzeit von
  Windows übersetzt (kein CUDA-Toolkit nötig); C++-Rahmenprogramm `native/gpu/mandel_gpu.cpp` rechnet in Streifen zu
  128 Zeilen (Windows bricht GPU-Aufträge > 2 s ab), färbt auf der CPU ein (OpenMP) und liefert Kacheln wie die anderen.
  Reine Rechenzeit ohne Bildübertragung, Median aus 3:

  | Einstellung | Kardioide | Rust SIMD (48 Thr.) | GPU double | GPU float |
  |---|---|---|---|---|
  | 1600 × 2560, 5000 It. | nein | 0,067 s | 0,173 s (0,4×) | 0,028 s (2,4×) |
  | 1600 × 2560, 5000 It. | ja | 0,031 s | 0,101 s (0,3×) | 0,027 s (1,2×) |
  | 1600 × 2560, 20 000 It. | nein | 0,238 s | 0,575 s (0,4×) | 0,046 s (5,2×) |
  | 1600 × 2560, 20 000 It. | ja | 0,109 s | 0,311 s (0,4×) | 0,039 s (2,8×) |
  | 3840 × 6144, 5000 It. | nein | 0,288 s | 0,846 s (0,3×) | 0,109 s (2,6×) |
  | 3840 × 6144, 5000 It. | ja | 0,078 s | 0,388 s (0,2×) | 0,087 s (0,9×) |

  - GPU-Start (Gerät öffnen, Shader übersetzen) ≈ 0,45 s, getrennt ausgewiesen. Die reine GPU-Rechenzeit liegt in float
    bei 0,01–0,03 s; der Rest ist Zurückkopieren und Einfärben auf der CPU. Über den Server mit Live-Kacheln ≈ 0,08 s.
  - **double ist auf dieser Grafikkarte langsamer als die CPU:** Die RTX 3090 rechnet double nur mit 1/64 der
    float-Geschwindigkeit. Rechenkarten (z. B. NVIDIA A100/H100) haben dafür viel mehr double-Leistung.
  - **Genauigkeit:** float weicht in der Gesamtansicht bei 0,3 % der Pixel ab, in tiefen Zooms bei 4–17 % (sichtbar
    andere Strukturen; bei starkem Zoom reicht float gar nicht mehr). Auch double weicht bei 0,01–0,5 % der Pixel ab.
    FMA ist nicht die Erklärung (C mit FMA weicht anders ab); der Grafiktreiber übersetzt den Shader auf eigene Weise.
  - Die GPU-Last erscheint nicht in der CPU-Heatmap.
- **Speicherbedarf der Worker** (gefunden beim Pakettest: „Auslagerungsdatei zu klein“ bei vielen gleichzeitigen Workern):
  numpy bringt OpenBLAS mit, das in jedem Prozess Puffer für alle 48 CPU-Threads anlegt – ≈ 800 MB je Mandelbrot-Worker,
  37,6 GB für 48 Worker; zudem lud jeder Worker den ganzen Webserver. Lösung: `OPENBLAS_NUM_THREADS=1` usw. in
  `server.py` vor dem ersten Laden von numpy, und `server.py` als winzige Startdatei (Anwendung in `app.py`, Worker-Hilfen
  in `worker_util.py`/`lastgen.py`). Ergebnis: 62 MB je Mandelbrot-Worker (2,9 GB für 48), Pi-Worker 19 MB,
  Webserver 88 statt 834 MB, Pool-Start 5,7 statt 10,2 s; Rechengeschwindigkeit unverändert.
- **Pi-Skalierungstest** (08.11.2026, 10 Mio. Stellen, gmpy2 2.3, Median aus 3; Zeiten in s):

  | Worker | 1 | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 |
  |---|---|---|---|---|---|---|---|---|---|
  | Gesamt | 8,33 | 6,41 | 5,31 | 4,84 | 4,62 | 4,57 | 3,95 | 3,97 | 4,72 |
  | Beschleunigung | 1,0 | 1,3 | 1,6 | 1,7 | 1,8 | 1,8 | 2,1 | 2,1 | 1,8 |
  | Reihe (parallel) | 5,56 | 3,10 | 1,47 | 0,73 | 0,46 | 0,36 | 0,18 | 0,16 | 0,17 |
  | Zusammenführen | – | 0,55 | 1,12 | 1,42 | 1,46 | 1,52 | 1,38 | 1,38 | 1,80 |
  | Wurzel + Division | 1,57 | 1,59 | 1,56 | 1,52 | 1,55 | 1,56 | 1,36 | 1,40 | 1,58 |
  | Dezimalumwandlung | 1,20 | 1,16 | 1,16 | 1,16 | 1,15 | 1,14 | 1,03 | 1,03 | 1,16 |

  - **Amdahlsches Gesetz** in Reinform: Die parallele Reihe schrumpft von 5,6 s auf 0,2 s (≈ 33×), aber Wurzel, Division
    und Dezimalumwandlung (zusammen ≈ 2,7 s) laufen immer auf einem Kern, und die obersten Multiplikationen beim
    Zusammenführen ebenfalls. Höchstens ≈ 2,1×; mit 48 Workern wird es wieder langsamer (mehr Zusammenführen und
    mehr Datentransport zwischen den Prozessen).
  - Gemessene Varianten (10 Mio. Stellen, 48 Worker): 1 Block je Worker ist besser als 2 oder 4 (4,6 s statt 5,2–5,4 s);
    Zusammenführen auf die Worker verteilen ist besser als alles im Hauptprozess (4,6 s statt 5,8 s).
  - 1 Mio. Stellen: 0,46 s mit 1 Worker, 0,28 s mit 8 Workern. Alle Läufe stimmen mit mpmath überein.
  - Die seriellen Schritte (letzte Multiplikation, Wurzel, Division, Umwandlung) laufen in einem Worker-Prozess,
    nicht im Server: GMP gibt das GIL nicht frei, der Server wäre sonst sekundenlang taub. Gemessen bei 50 Mio.
    Stellen (32,8 s, davon 17 s ein einziger serieller Schritt): Der Server antwortete durchgehend in höchstens 0,22 s.
  - Ein C#-Gegenstück wurde bewusst nicht gebaut: `System.Numerics.BigInteger` hat keine so schnellen Verfahren für
    riesige Zahlen wie GMP und wäre bei Millionen Stellen um ein Vielfaches langsamer. Der Vergleich würde dann die
    Bibliothek messen, nicht die Parallelisierung.
- Last-Prozesse und Mandelbrot-Worker laufen mit Priorität „niedriger als normal“, damit Browser und
  Webserver auch bei 100 % Last bedienbar bleiben. Worker beenden sich selbst, wenn der Server wegfällt.
- Behobener Fehler (08.11.2026): Ein Klick auf „Start“ beim Last-Generator konnte den Messtakt dauerhaft
  anhalten (Live-Ansicht eingefroren), weil der Status während des Prozessstarts unvollständig war.
- Windows legt wenige Worker oft dicht zusammen: 4 Mandelbrot-Worker liefen in drei Tests auf den Threads 24–27(28),
  also auf 2 Kernen mit jeweils beiden SMT-Threads, obwohl 22 Kerne frei waren.
- **Platzierung der Worker** (Einstellung „Platzierung“, CPU-Affinität je Worker). Messung am 08.11.2026,
  1600 × 2560 (gedreht), 5000 Iterationen, numba, 128-px-Kacheln, Median aus 3 Läufen:

  | Worker | 1 | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 |
  |---|---|---|---|---|---|---|---|---|---|
  | Windows entscheidet (s) | 6,18 | 3,27 | 1,72 | 0,93 | 0,72 | 0,56 | 0,51 | 0,40 | 0,34 |
  | 1 Thread je Kern zuerst (s) | 6,23 | 3,14 | 1,64 | 0,90 | 0,66 | 0,55 | 0,49 | 0,39 | 0,34 |
  | kompakt (s) | 6,24 | 3,39 | 1,76 | 0,96 | 0,71 | 0,58 | 0,49 | 0,39 | 0,35 |
  | Beschleunigung „verteilt“ | 1,0 | 2,0 | 3,8 | 7,0 | 9,5 | 11,3 | 12,8 | 16,0 | 18,2 |

  - Die Platzierung ändert wenig: „1 Thread je Kern zuerst“ ist bei 2–16 Workern 3–10 % schneller als
    „Windows entscheidet“, bei 48 Workern sind alle gleich.
  - **SMT bremst Mandelbrot kaum**: 2 Worker auf beiden Threads *eines* Kerns sind nur 8 % langsamer als auf
    2 Kernen; 24 Worker auf 12 Kernen nur ≈5 % langsamer als auf 24 Kernen. Grund: Jeder Rechenschritt wartet auf
    den vorherigen, ein Thread lastet die Rechenwerke nicht aus, und der zweite Thread füllt die Lücken.
  - **Hauptbremse bei vielen Workern ist die kurze Laufzeit** (0,3–0,5 s): Leerlauf am Ende (die letzten Kacheln) und Verwaltung.
    Gegenprobe mit 4-facher Arbeit (20 000 Iterationen, „verteilt“): 1 Worker 24,4 s, 24 Worker 1,58 s (15,4×),
    48 Worker 0,98 s (**24,8×**). Die CPU-Zeit aller Worker bleibt dabei bei ≈24 s, verloren geht reine Wartezeit.
- **Aufwendige Kacheln zuerst + C#-Vergleich** (08.11.2026, 1600 × 2560 gedreht, 5000 Iterationen, 128-px-Kacheln,
  Platzierung „Windows“, Median aus 3 Läufen; Zeit in s, in Klammern die Beschleunigung):

  | Worker | numba zeilenweise | numba aufwendige zuerst | C# zeilenweise | C# aufwendige zuerst |
  |---|---|---|---|---|
  | 1 | 6,18 (1,0×) | 6,22 (1,0×) | 6,13 (1,0×) | 6,13 (1,0×) |
  | 8 | 0,93 (6,6×) | 0,94 (6,6×) | 0,86 (7,1×) | 0,85 (7,2×) |
  | 16 | 0,56 (11,0×) | 0,54 (11,5×) | 0,52 (11,9×) | 0,47 (13,1×) |
  | 24 | 0,51 (12,1×) | 0,40 (15,5×) | 0,43 (14,2×) | 0,36 (17,1×) |
  | 32 | 0,40 (15,5×) | 0,36 (17,2×) | 0,33 (18,9×) | 0,28 (21,6×) |
  | 48 | 0,34 (18,4×) | 0,29 (21,8×) | 0,27 (22,8×) | **0,24 (25,1×)** |
  | Start | 1,7–5,8 s (Pool) | 1,7–5,8 s | 0,14 s (.NET) | 0,14 s |

  - **„Aufwendige zuerst“** (Aufwandsschätzung mit 8×8 Stichproben je Kachel, ≈ 15 ms, in der Zeit enthalten) bringt bei
    24–48 Workern 10–22 % weniger Laufzeit, bei wenigen Workern nichts (dort gibt es kaum Leerlauf am Ende).
  - **C# ist mit 1 Thread genauso schnell wie numba** (6,13 vs. 6,18 s): Beide erzeugen fast den gleichen Maschinencode.
    Der Vorteil von C# liegt beim Drumherum: echte Threads in einem Prozess, Start in 0,14 s statt mehrerer Sekunden,
    keine Datenübergabe zwischen Prozessen. Bei 48 Threads ist C# dadurch rund 20 % schneller.
  - C# liefert **bitgenau dasselbe Bild** wie numba (Gegenprobe: 0 von 256 000 Pixeln verschieden, gleiche Zahl von Punkten
    in der Menge).
- **C# + SIMD (AVX2)** und binäre Kachelübergabe (08.11.2026, gleiche Parameter, Median aus 3; Zeit in s, Beschleunigung):

  | Worker | numba aufwendige zuerst | C# zeilenweise | C# aufwendige zuerst | C# SIMD zeilenweise | C# SIMD aufwendige zuerst |
  |---|---|---|---|---|---|
  | 1 | 6,22 (1,0×) | 6,09 (1,0×) | 6,12 (1,0×) | 1,65 (1,0×) | 1,66 (1,0×) |
  | 8 | 0,94 (6,6×) | 0,83 (7,3×) | 0,80 (7,7×) | 0,23 (7,3×) | 0,23 (7,2×) |
  | 24 | 0,40 (15,5×) | 0,40 (15,4×) | 0,36 (17,2×) | 0,11 (15,0×) | 0,11 (15,3×) |
  | 48 | 0,29 (21,8×) | 0,23 (26,9×) | 0,23 (26,2×) | **0,070 (23,6×)** | 0,077 (21,6×) |

  - SIMD: 4 Pixel je Thread mit `Vector256<double>` (AVX2; AVX-512 hat der 3960X nicht). Kein FMA, deshalb **bitgenau
    dasselbe Bild** (geprüft, auch mit Bildbreiten, die nicht durch 4 teilbar sind). Mit 1 Thread **3,7× schneller**.
  - Gesamtergebnis bei 48 Threads: **C# SIMD 0,070 s gegenüber 0,29 s mit numba (≈ 4×)** und 6,2 s mit einem Python-Prozess (≈ 89×).
  - SIMD skaliert relativ etwas schlechter (23,6× statt 26,9×): Die Laufzeit ist so kurz, dass Verwaltung zählt,
    und SMT bringt weniger (gemessen: 2 SIMD-Threads auf 1 Kern 11 % langsamer als auf 2 Kernen, skalar nur 5 %).
    Ohne Kachelübergabe und mit 20 000 Iterationen skaliert auch SIMD auf ≈ 27×.
  - „Aufwendige zuerst“ lohnt sich bei SIMD nicht mehr: Die Schätzung (≈ 13 ms) dauert bei 70 ms Gesamtzeit zu lange.
  - Die Kachelübergabe von C# an den Server war anfangs base64-JSON. Das bremste C# bei kurzen Laufzeiten deutlich
    (0,116 s statt 0,070 s bei SIMD). Jetzt binär: kurze Kopfzeile plus rohe RGB-Bytes.
  - Diagramm: Umschaltung „Beschleunigung“ / „Laufzeit (s, logarithmisch)“ (direkt per Link: `http://127.0.0.1:8000/#zeit`).
  - Weitere Ideen: kleinere Kacheln nur am Ende; numba-Kern ebenfalls mehrere Pixel gleichzeitig rechnen lassen.
- Die Website erklärt Heatmap, Worker-Färbung und Skalierungsdiagramm in aufklappbaren Abschnitten („Was sehe ich hier?“).
- Sehr kleine Kacheln (64 px und weniger) erzeugen spürbar Verwaltungsaufwand im Hauptprozess;
  128 px ist ein guter Standardwert.
- Alle Erklärungen auf der Seite sind beim Laden eingeklappt und lassen sich bei Bedarf öffnen.

## Begriffe kurz erklärt

Alphabetisch, mit Link zu einer weiterführenden Quelle.

- **0.0.0.0:** Server-Einstellung „auf allen Netzwerkkarten erreichbar“. Der Monitor nutzt das bewusst nicht, sondern nur 127.0.0.1.
- **127.0.0.1 (localhost):** Adresse des eigenen PCs. Der Server lauscht nur dort und ist deshalb von anderen Rechnern aus nicht erreichbar. <https://de.wikipedia.org/wiki/Localhost>
- **Amdahlsches Gesetz:** Der nicht parallelisierbare Anteil eines Programms begrenzt die mögliche Beschleunigung, egal wie viele Kerne man einsetzt (siehe Pi). <https://de.wikipedia.org/wiki/Amdahlsches_Gesetz>
- **API:** Schnittstelle, über die die Seite (oder ein Skript) den Server steuert, z. B. /api/mandel/start. <https://de.wikipedia.org/wiki/Programmierschnittstelle>
- **Assembler (MASM):** Prozessorbefehle in lesbarer Form, von Hand geschrieben. MASM ist der Microsoft Macro Assembler. <https://learn.microsoft.com/de-de/cpp/assembler/masm/microsoft-macro-assembler-reference>
- **„Aufwendige Kacheln zuerst“:** Reihenfolge, bei der eine grobe Vorab-Schätzung die rechenaufwendigsten Kacheln an den Anfang stellt, damit am Ende keine lange Kachel allein übrig bleibt.
- **AVX-512:** Nachfolger von AVX2 mit 512-Bit-Registern (8 double gleichzeitig). Der Threadripper 3960X hat es nicht; neuere Prozessoren teils schon. <https://de.wikipedia.org/wiki/AVX-512>
- **AVX2:** SIMD-Befehlssatz aktueller x86-Prozessoren; 256-Bit-Register fassen 4 Kommazahlen (double), also 4 Bildpunkte je Befehl. <https://de.wikipedia.org/wiki/Advanced_Vector_Extensions>
- **base64:** Verfahren, Binärdaten (hier Bildkacheln) als reinen Text zu verschicken; etwa ein Drittel größer als das Original. <https://de.wikipedia.org/wiki/Base64>
- **Binary Splitting:** Rechentrick, der die Reihenglieder paarweise zu großen Brüchen zusammenfasst; die Teilstücke lassen sich parallel berechnen, die letzte Division nicht. <https://en.wikipedia.org/wiki/Binary_splitting>
- **bitgenau:** Jedes Byte des Ergebnisses ist identisch – hier: 0 Pixel Unterschied zwischen den Rechenverfahren.
- **C / C++:** Klassische, maschinennahe Sprachen. Hier mit dem Microsoft-Compiler (MSVC) aus Visual Studio übersetzt. <https://learn.microsoft.com/de-de/cpp/>
- **C# / .NET:** Programmiersprache und Laufzeitumgebung von Microsoft; echte Threads, Übersetzung in Maschinencode zur Laufzeit. <https://learn.microsoft.com/de-de/dotnet/csharp/>
- **Cache (L1/L2/L3):** Schneller Zwischenspeicher im Prozessor. L1/L2 gehören je einem Kern, L3 teilen sich die Kerne eines CCX. <https://de.wikipedia.org/wiki/Cache>
- **CCX (Core Complex):** Bei AMD-Zen-Prozessoren eine Gruppe von Kernen mit gemeinsamem L3-Cache; beim 3960X 8 CCX zu je 3 Kernen. Im Monitor „L3-Gruppe“. <https://en.wikipedia.org/wiki/Zen_2>
- **Chudnovsky-Formel:** Sehr schnell konvergierende Reihe für Pi: etwa 14 neue Stellen je Glied. <https://en.wikipedia.org/wiki/Chudnovsky_algorithm>
- **Compiler-Schalter /O2, /arch:AVX2, /fp:precise, /MT:** Optimieren, AVX2-Befehle erlauben, Rechnung exakt wie geschrieben (kein FMA), Laufzeitbibliothek fest einbinden (keine Zusatz-DLLs nötig). <https://learn.microsoft.com/de-de/cpp/build/reference/compiler-options-listed-by-category>
- **CPU-Affinität (Platzierung):** Festlegung, auf welchen Threads ein Prozess laufen darf. Damit testet der Monitor „1 Thread je Kern zuerst“ gegen „kompakt“. <https://en.wikipedia.org/wiki/Processor_affinity>
- **Digitale Signatur (Code-Signatur):** Elektronische Unterschrift eines Herstellers an einer .exe; signierte, verbreitete Programme lösen seltener Warnungen aus. Die Programme des Kern-Monitors sind nicht signiert. <https://en.wikipedia.org/wiki/Code_signing>
- **Direct3D 11 Compute-Shader / HLSL:** Programm, das auf der Grafikkarte läuft; geschrieben in HLSL, gestartet über Direct3D 11 (funktioniert mit jeder aktuellen Grafikkarte unter Windows). <https://learn.microsoft.com/de-de/windows/win32/direct3d11/direct3d-11-advanced-stages-compute-shader>
- **double / float:** Kommazahlen mit doppelter (≈ 16 Stellen) bzw. einfacher Genauigkeit (≈ 7 Stellen) nach IEEE 754. Spiele-Grafikkarten sind mit float viel schneller. <https://de.wikipedia.org/wiki/IEEE_754>
- **DXGI:** Windows-Schnittstelle, über die der Monitor die vorhandenen Grafikkarten und ihren Speicher erkennt. <https://learn.microsoft.com/de-de/windows/win32/direct3ddxgi/dx-graphics-dxgi>
- **Embedded Python:** Offizielles, schlankes Python zum Mitgeben in einem Ordner, ohne Installation. Steckt im Paket „Komplett“. <https://docs.python.org/3/using/windows.html#the-embeddable-package>
- **FastAPI / uvicorn:** Python-Bausteine für den Webserver: FastAPI beschreibt die Schnittstellen, uvicorn liefert sie aus. <https://fastapi.tiangolo.com/>
- **Fehlalarm (False Positive):** Ein Virenscanner hält ein harmloses Programm für gefährlich, weil es sich ähnlich verhält wie Schadsoftware (z. B. unsignierte .exe, volle Auslastung aller Kerne). Siehe „Hinweis zum Virenscanner“. <https://de.wikipedia.org/wiki/Falsch_positiv>
- **FMA (Fused Multiply-Add):** Multiplikation und Addition in einem Schritt mit nur einer Rundung. Schneller, verändert aber die letzte Stelle – und damit einzelne Bildpunkte. <https://en.wikipedia.org/wiki/Multiply%E2%80%93accumulate_operation>
- **GIL (Global Interpreter Lock):** Sperre im Standard-Python: Nur ein Thread führt gleichzeitig Python-Code aus. Deshalb nutzt der Monitor für Python Prozesse statt Threads. <https://docs.python.org/3/glossary.html#term-global-interpreter-lock>
- **gmpy2 / GMP:** Bibliothek für sehr große Zahlen mit beliebig vielen Stellen; Grundlage der Pi-Berechnung. <https://gmpy2.readthedocs.io/>
- **GPU (Grafikkarte):** Prozessor mit Tausenden einfacher Recheneinheiten; ideal, wenn sehr viele gleichartige Rechnungen anfallen (z. B. je Bildpunkt eine). <https://de.wikipedia.org/wiki/Grafikprozessor>
- **Heatmap:** Farbige Kachelansicht: je Thread ein Feld, Farbe = aktuelle Auslastung. <https://de.wikipedia.org/wiki/Heatmap>
- **Intrinsics:** Funktionen in C/C++/Rust, die direkt einem Prozessorbefehl (z. B. AVX2) entsprechen; SIMD ohne Assembler. <https://learn.microsoft.com/de-de/cpp/intrinsics/compiler-intrinsics>
- **Iterationen (max_iter):** Wie oft z → z² + c höchstens wiederholt wird. Mehr Iterationen = feinere Ränder, aber mehr Rechenzeit (besonders im schwarzen Inneren).
- **JIT (Just-in-time-Übersetzung):** Code wird erst während des Programmlaufs in Maschinencode übersetzt; der erste Aufruf dauert daher länger. <https://de.wikipedia.org/wiki/Just-in-time-Kompilierung>
- **JSON / CSV:** Textformate für Messdaten: JSON für strukturierte Daten (eine Datei je Messung), CSV als Tabelle, die z. B. Excel öffnen kann. <https://de.wikipedia.org/wiki/JavaScript_Object_Notation>
- **Kachel:** Rechteckiger Bildausschnitt (Standard 128 × 128 Pixel), die kleinste Arbeitseinheit eines Workers.
- **Kardioide und Periode-2-Kreis:** Die herzförmige Hauptfläche und der große Kreis links davon gehören sicher zur Mandelbrot-Menge. Eine kurze Formel erkennt diese Punkte, ohne sie bis zur Höchstzahl durchzurechnen. <https://de.wikipedia.org/wiki/Kardioide>
- **Kern (Prozessorkern):** Eigenständiges Rechenwerk im Prozessor. Der Threadripper 3960X hat 24 Kerne. <https://de.wikipedia.org/wiki/Mehrkernprozessor>
- **Lastverteilung (dynamisch):** Wer mit seiner Kachel fertig ist, holt sich die nächste. So bleiben keine Kerne untätig, obwohl Kacheln unterschiedlich lange dauern. <https://de.wikipedia.org/wiki/Lastverteilung_(Informatik)>
- **Mandelbrot-Menge:** Bekanntes Fraktal: Für jeden Bildpunkt wird z → z² + c wiederholt, bis der Wert „entkommt“ oder die Höchstzahl erreicht ist. Jeder Punkt ist unabhängig – ideal für Parallelisierung. <https://de.wikipedia.org/wiki/Mandelbrot-Menge>
- **Median:** Mittlerer Wert einer sortierten Messreihe; unempfindlicher gegen Ausreißer als der Durchschnitt. Wird bei mehreren Läufen gewertet. <https://de.wikipedia.org/wiki/Median>
- **mpmath:** Python-Bibliothek für Rechnen mit beliebiger Genauigkeit; dient als unabhängige Gegenprobe für die Pi-Stellen. <https://mpmath.org/>
- **NUMA:** Non-Uniform Memory Access: Bei großen Systemen ist Speicher je nach Kern unterschiedlich schnell erreichbar. Der 3960X hat einen NUMA-Knoten. <https://de.wikipedia.org/wiki/Non-Uniform_Memory_Access>
- **numba:** Übersetzt ausgewählte Python-Funktionen beim ersten Aufruf in Maschinencode (JIT) und macht sie so etwa so schnell wie C. <https://numba.pydata.org/>
- **numpy:** Python-Bibliothek für Rechnen mit ganzen Zahlenfeldern (Arrays). Schnell bei einfachen Feldoperationen, aber nicht ideal für Mandelbrot. <https://numpy.org/>
- **OpenBLAS:** Mathe-Bibliothek in numpy, die selbst Threads startet. Im Monitor auf 1 Thread je Prozess begrenzt, sonst braucht jeder Worker ~800 MB. <https://www.openblas.net/>
- **pip:** Paketverwaltung von Python; installiert Erweiterungen wie numba oder FastAPI. <https://pip.pypa.io/>
- **ProcessPoolExecutor:** Python-Baustein, der einen Vorrat an Worker-Prozessen verwaltet und Aufgaben an sie verteilt. <https://docs.python.org/3/library/concurrent.futures.html>
- **Prozess:** Laufendes Programm mit eigenem Speicher. Mehrere Prozesse laufen unabhängig, tauschen Daten aber nur über Umwege aus. <https://de.wikipedia.org/wiki/Prozess_(Informatik)>
- **Prozessorgruppe:** Windows fasst höchstens 64 Threads zu einer Gruppe zusammen. Prozessoren mit mehr Threads haben mehrere Gruppen; ein Prozess läuft normalerweise nur in einer. <https://learn.microsoft.com/de-de/windows/win32/procthread/processor-groups>
- **psutil:** Python-Bibliothek, die Auslastung, Speicher und Prozesse abfragt; liefert die Werte für die Kern-Anzeige. <https://psutil.readthedocs.io/>
- **Python:** Verbreitete Skriptsprache; hier für Webserver, Steuerung und zwei Rechenverfahren. <https://www.python.org/>
- **Quarantäne:** Abgeschotteter Bereich des Virenscanners für verdächtige Dateien; von dort lassen sie sich wiederherstellen. <https://de.wikipedia.org/wiki/Antivirenprogramm>
- **Rust:** Moderne Systemsprache mit C-ähnlicher Geschwindigkeit; der Übersetzer verhindert typische Fehler beim Arbeiten mit Threads. <https://www.rust-lang.org/>
- **rustup / cargo:** rustup installiert und aktualisiert Rust; cargo übersetzt Rust-Programme und lädt benötigte Bibliotheken. <https://rustup.rs/>
- **Scheduler:** Teil von Windows, der entscheidet, welcher Thread wann auf welchem Kern läuft (Platzierung „Windows entscheidet“). <https://de.wikipedia.org/wiki/Prozess-Scheduler>
- **Seepferdchental:** Bekannter Ausschnitt der Mandelbrot-Menge zwischen Hauptfläche und Periode-2-Kreis; sehr fein verästelt und daher rechenaufwendig. <https://de.wikipedia.org/wiki/Mandelbrot-Menge>
- **Self-contained Single-File:** .NET-Programm, das die Laufzeitumgebung in einer einzigen .exe mitbringt; läuft ohne installiertes .NET. <https://learn.microsoft.com/de-de/dotnet/core/deploying/single-file/overview>
- **SIMD:** Single Instruction, Multiple Data: Ein Befehl rechnet mehrere Zahlen gleichzeitig. <https://de.wikipedia.org/wiki/SIMD>
- **Skalierung, Beschleunigung, Effizienz:** Beschleunigung = Zeit mit 1 Worker ÷ Zeit mit n Workern. Effizienz = Beschleunigung ÷ n (100 % = perfekt). <https://de.wikipedia.org/wiki/Speedup>
- **SmartScreen:** Windows-Schutz, der vor unbekannten, nicht signierten Programmen warnt („Der Computer wurde durch Windows geschützt“). <https://learn.microsoft.com/de-de/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/>
- **SMT (Simultaneous Multithreading, bei Intel „Hyper-Threading“):** Ein Kern bearbeitet zwei Befehlsströme gleichzeitig und füllt damit Lücken in seinen Rechenwerken. Bringt meist 0–30 %, nicht 100 %. <https://de.wikipedia.org/wiki/Simultaneous_Multithreading>
- **Thread (Hardware-Thread, logischer Prozessor):** Was Windows als „CPU“ zählt. Mit SMT bietet jeder Kern 2 Threads, also 48 beim 3960X. <https://de.wikipedia.org/wiki/Thread_(Informatik)>
- **Thread (Software):** Ausführungsstrang innerhalb eines Prozesses; alle Threads teilen sich den Speicher und starten viel schneller als Prozesse. <https://de.wikipedia.org/wiki/Thread_(Informatik)>
- **vcomp140.dll / OpenMP:** OpenMP ist ein Standard, mit dem C/C++-Programme Schleifen auf Threads verteilen; vcomp140.dll ist Microsofts Laufzeitbibliothek dafür und liegt dem Paket bei. <https://learn.microsoft.com/de-de/cpp/parallel/openmp/openmp-in-visual-cpp>
- **Vector256:** .NET-Datentyp für ein 256-Bit-Register (4 double); damit nutzt C# AVX2. <https://learn.microsoft.com/de-de/dotnet/api/system.runtime.intrinsics.vector256>
- **VirusTotal:** Kostenloser Dienst, der eine Datei mit rund 70 Virenscannern gleichzeitig prüft. <https://www.virustotal.com/>
- **Visual Studio Build Tools:** Microsofts Compiler für C, C++ und Assembler ohne die volle Entwicklungsumgebung; kostenlos. <https://visualstudio.microsoft.com/de/downloads/>
- **WebSocket:** Dauerhafte Verbindung zwischen Browser und Server; darüber kommen die Auslastungswerte jede Sekunde ohne Neuladen. <https://de.wikipedia.org/wiki/WebSocket>
- **winget:** Paketverwaltung von Windows; installiert Programme wie Python, .NET oder Rust per Befehlszeile. <https://learn.microsoft.com/de-de/windows/package-manager/winget/>
- **Worker:** Ein Prozess oder Thread, der Kacheln abarbeitet. Die Worker-Zahl stellt man im Monitor ein (1–48).
- **x64:** 64-Bit-Befehlssatz der heutigen Intel- und AMD-Prozessoren (auch x86-64 oder AMD64). <https://de.wikipedia.org/wiki/X64>
