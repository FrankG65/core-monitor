"""Glossary – the single source for README.md / README.de.md, the web page (static/index.html) and the project reports.

Each term exists in German (list G) and English (dict EN). After changing the list:
    python tools\\glossar.py                         regenerate README files and web page
    python tools\\glossar.py check                   fetch all links and report broken ones
    python tools\\glossar.py report <file.html> de|en   replace chapter 10 in the HTML source of a report
"""
import html, sys, urllib.request
from pathlib import Path

G = [
    ("Prozessor und Hardware", [
        ("Kern (Prozessorkern)", "Eigenständiges Rechenwerk im Prozessor. Der Threadripper 3960X hat 24 Kerne.",
         "https://de.wikipedia.org/wiki/Mehrkernprozessor"),
        ("Thread (Hardware-Thread, logischer Prozessor)", "Was Windows als „CPU“ zählt. Mit SMT bietet jeder Kern 2 Threads, also 48 beim 3960X.",
         "https://de.wikipedia.org/wiki/Thread_(Informatik)"),
        ("SMT (Simultaneous Multithreading, bei Intel „Hyper-Threading“)", "Ein Kern bearbeitet zwei Befehlsströme gleichzeitig und füllt damit Lücken in seinen Rechenwerken. Bringt meist 0–30 %, nicht 100 %.",
         "https://de.wikipedia.org/wiki/Simultaneous_Multithreading"),
        ("CCX (Core Complex)", "Bei AMD-Zen-Prozessoren eine Gruppe von Kernen mit gemeinsamem L3-Cache; beim 3960X 8 CCX zu je 3 Kernen. Im Monitor „L3-Gruppe“.",
         "https://en.wikipedia.org/wiki/Zen_2"),
        ("Cache (L1/L2/L3)", "Schneller Zwischenspeicher im Prozessor. L1/L2 gehören je einem Kern, L3 teilen sich die Kerne eines CCX.",
         "https://de.wikipedia.org/wiki/Cache"),
        ("NUMA", "Non-Uniform Memory Access: Bei großen Systemen ist Speicher je nach Kern unterschiedlich schnell erreichbar. Der 3960X hat einen NUMA-Knoten.",
         "https://de.wikipedia.org/wiki/Non-Uniform_Memory_Access"),
        ("CPU-Affinität (Platzierung)", "Festlegung, auf welchen Threads ein Prozess laufen darf. Damit testet der Monitor „1 Thread je Kern zuerst“ gegen „kompakt“.",
         "https://en.wikipedia.org/wiki/Processor_affinity"),
        ("GPU (Grafikkarte)", "Prozessor mit Tausenden einfacher Recheneinheiten; ideal, wenn sehr viele gleichartige Rechnungen anfallen (z. B. je Bildpunkt eine).",
         "https://de.wikipedia.org/wiki/Grafikprozessor"),
    ]),
    ("Parallelisierung und Messung", [
        ("Prozess", "Laufendes Programm mit eigenem Speicher. Mehrere Prozesse laufen unabhängig, tauschen Daten aber nur über Umwege aus.",
         "https://de.wikipedia.org/wiki/Prozess_(Informatik)"),
        ("Thread (Software)", "Ausführungsstrang innerhalb eines Prozesses; alle Threads teilen sich den Speicher und starten viel schneller als Prozesse.",
         "https://de.wikipedia.org/wiki/Thread_(Informatik)"),
        ("Worker", "Ein Prozess oder Thread, der Kacheln abarbeitet. Die Worker-Zahl stellt man im Monitor ein (1–48).", None),
        ("Skalierung, Beschleunigung, Effizienz", "Beschleunigung = Zeit mit 1 Worker ÷ Zeit mit n Workern. Effizienz = Beschleunigung ÷ n (100 % = perfekt).",
         "https://de.wikipedia.org/wiki/Speedup"),
        ("Amdahlsches Gesetz", "Der nicht parallelisierbare Anteil eines Programms begrenzt die mögliche Beschleunigung, egal wie viele Kerne man einsetzt (siehe Pi).",
         "https://de.wikipedia.org/wiki/Amdahlsches_Gesetz"),
        ("Lastverteilung (dynamisch)", "Wer mit seiner Kachel fertig ist, holt sich die nächste. So bleiben keine Kerne untätig, obwohl Kacheln unterschiedlich lange dauern.",
         "https://de.wikipedia.org/wiki/Lastverteilung_(Informatik)"),
        ("Median", "Mittlerer Wert einer sortierten Messreihe; unempfindlicher gegen Ausreißer als der Durchschnitt. Wird bei mehreren Läufen gewertet.",
         "https://de.wikipedia.org/wiki/Median"),
        ("Heatmap", "Farbige Kachelansicht: je Thread ein Feld, Farbe = aktuelle Auslastung.", "https://de.wikipedia.org/wiki/Heatmap"),
    ]),
    ("Python", [
        ("Python", "Verbreitete Skriptsprache; hier für Webserver, Steuerung und zwei Rechenverfahren.", "https://www.python.org/"),
        ("GIL (Global Interpreter Lock)", "Sperre im Standard-Python: Nur ein Thread führt gleichzeitig Python-Code aus. Deshalb nutzt der Monitor für Python Prozesse statt Threads.",
         "https://docs.python.org/3/glossary.html#term-global-interpreter-lock"),
        ("ProcessPoolExecutor", "Python-Baustein, der einen Vorrat an Worker-Prozessen verwaltet und Aufgaben an sie verteilt.",
         "https://docs.python.org/3/library/concurrent.futures.html"),
        ("numba", "Übersetzt ausgewählte Python-Funktionen beim ersten Aufruf in Maschinencode (JIT) und macht sie so etwa so schnell wie C.",
         "https://numba.pydata.org/"),
        ("JIT (Just-in-time-Übersetzung)", "Code wird erst während des Programmlaufs in Maschinencode übersetzt; der erste Aufruf dauert daher länger.",
         "https://de.wikipedia.org/wiki/Just-in-time-Kompilierung"),
        ("numpy", "Python-Bibliothek für Rechnen mit ganzen Zahlenfeldern (Arrays). Schnell bei einfachen Feldoperationen, aber nicht ideal für Mandelbrot.",
         "https://numpy.org/"),
        ("OpenBLAS", "Mathe-Bibliothek in numpy, die selbst Threads startet. Im Monitor auf 1 Thread je Prozess begrenzt, sonst braucht jeder Worker ~800 MB.",
         "https://www.openblas.net/"),
        ("gmpy2 / GMP", "Bibliothek für sehr große Zahlen mit beliebig vielen Stellen; Grundlage der Pi-Berechnung.", "https://gmpy2.readthedocs.io/"),
        ("mpmath", "Python-Bibliothek für Rechnen mit beliebiger Genauigkeit; dient als unabhängige Gegenprobe für die Pi-Stellen.", "https://mpmath.org/"),
        ("Embedded Python", "Offizielles, schlankes Python zum Mitgeben in einem Ordner, ohne Installation. Steckt im Paket „Komplett“.",
         "https://docs.python.org/3/using/windows.html#the-embeddable-package"),
    ]),
    ("Sprachen und Werkzeuge", [
        ("C# / .NET", "Programmiersprache und Laufzeitumgebung von Microsoft; echte Threads, Übersetzung in Maschinencode zur Laufzeit.",
         "https://learn.microsoft.com/de-de/dotnet/csharp/"),
        ("Self-contained Single-File", ".NET-Programm, das die Laufzeitumgebung in einer einzigen .exe mitbringt; läuft ohne installiertes .NET.",
         "https://learn.microsoft.com/de-de/dotnet/core/deploying/single-file/overview"),
        ("Rust", "Moderne Systemsprache mit C-ähnlicher Geschwindigkeit; der Übersetzer verhindert typische Fehler beim Arbeiten mit Threads.",
         "https://www.rust-lang.org/"),
        ("C / C++", "Klassische, maschinennahe Sprachen. Hier mit dem Microsoft-Compiler (MSVC) aus Visual Studio übersetzt.",
         "https://learn.microsoft.com/de-de/cpp/"),
        ("Assembler (MASM)", "Prozessorbefehle in lesbarer Form, von Hand geschrieben. MASM ist der Microsoft Macro Assembler.",
         "https://learn.microsoft.com/de-de/cpp/assembler/masm/microsoft-macro-assembler-reference"),
        ("Compiler-Schalter /O2, /arch:AVX2, /fp:precise, /MT", "Optimieren, AVX2-Befehle erlauben, Rechnung exakt wie geschrieben (kein FMA), Laufzeitbibliothek fest einbinden (keine Zusatz-DLLs nötig).",
         "https://learn.microsoft.com/de-de/cpp/build/reference/compiler-options-listed-by-category"),
        ("Intrinsics", "Funktionen in C/C++/Rust, die direkt einem Prozessorbefehl (z. B. AVX2) entsprechen; SIMD ohne Assembler.",
         "https://learn.microsoft.com/de-de/cpp/intrinsics/compiler-intrinsics"),
        ("Direct3D 11 Compute-Shader / HLSL", "Programm, das auf der Grafikkarte läuft; geschrieben in HLSL, gestartet über Direct3D 11 (funktioniert mit jeder aktuellen Grafikkarte unter Windows).",
         "https://learn.microsoft.com/de-de/windows/win32/direct3d11/direct3d-11-advanced-stages-compute-shader"),
    ]),
    ("Rechentechnik", [
        ("SIMD", "Single Instruction, Multiple Data: Ein Befehl rechnet mehrere Zahlen gleichzeitig.", "https://de.wikipedia.org/wiki/SIMD"),
        ("AVX2", "SIMD-Befehlssatz aktueller x86-Prozessoren; 256-Bit-Register fassen 4 Kommazahlen (double), also 4 Bildpunkte je Befehl.",
         "https://de.wikipedia.org/wiki/Advanced_Vector_Extensions"),
        ("FMA (Fused Multiply-Add)", "Multiplikation und Addition in einem Schritt mit nur einer Rundung. Schneller, verändert aber die letzte Stelle – und damit einzelne Bildpunkte.",
         "https://en.wikipedia.org/wiki/Multiply%E2%80%93accumulate_operation"),
        ("double / float", "Kommazahlen mit doppelter (≈ 16 Stellen) bzw. einfacher Genauigkeit (≈ 7 Stellen) nach IEEE 754. Spiele-Grafikkarten sind mit float viel schneller.",
         "https://de.wikipedia.org/wiki/IEEE_754"),
        ("bitgenau", "Jedes Byte des Ergebnisses ist identisch – hier: 0 Pixel Unterschied zwischen den Rechenverfahren.", None),
    ]),
    ("Mandelbrot und Pi", [
        ("Mandelbrot-Menge", "Bekanntes Fraktal: Für jeden Bildpunkt wird z → z² + c wiederholt, bis der Wert „entkommt“ oder die Höchstzahl erreicht ist. Jeder Punkt ist unabhängig – ideal für Parallelisierung.",
         "https://de.wikipedia.org/wiki/Mandelbrot-Menge"),
        ("Iterationen (max_iter)", "Wie oft z → z² + c höchstens wiederholt wird. Mehr Iterationen = feinere Ränder, aber mehr Rechenzeit (besonders im schwarzen Inneren).", None),
        ("Kachel", "Rechteckiger Bildausschnitt (Standard 128 × 128 Pixel), die kleinste Arbeitseinheit eines Workers.", None),
        ("Kardioide und Periode-2-Kreis", "Die herzförmige Hauptfläche und der große Kreis links davon gehören sicher zur Mandelbrot-Menge. Eine kurze Formel erkennt diese Punkte, ohne sie bis zur Höchstzahl durchzurechnen.",
         "https://de.wikipedia.org/wiki/Kardioide"),
        ("„Aufwendige Kacheln zuerst“", "Reihenfolge, bei der eine grobe Vorab-Schätzung die rechenaufwendigsten Kacheln an den Anfang stellt, damit am Ende keine lange Kachel allein übrig bleibt.", None),
        ("Chudnovsky-Formel", "Sehr schnell konvergierende Reihe für Pi: etwa 14 neue Stellen je Glied.", "https://en.wikipedia.org/wiki/Chudnovsky_algorithm"),
        ("Binary Splitting", "Rechentrick, der die Reihenglieder paarweise zu großen Brüchen zusammenfasst; die Teilstücke lassen sich parallel berechnen, die letzte Division nicht.",
         "https://en.wikipedia.org/wiki/Binary_splitting"),
    ]),
    ("Webseite und Weitergabe", [
        ("127.0.0.1 (localhost)", "Adresse des eigenen PCs. Der Server lauscht nur dort und ist deshalb von anderen Rechnern aus nicht erreichbar.",
         "https://de.wikipedia.org/wiki/Localhost"),
        ("FastAPI / uvicorn", "Python-Bausteine für den Webserver: FastAPI beschreibt die Schnittstellen, uvicorn liefert sie aus.", "https://fastapi.tiangolo.com/"),
        ("WebSocket", "Dauerhafte Verbindung zwischen Browser und Server; darüber kommen die Auslastungswerte jede Sekunde ohne Neuladen.",
         "https://de.wikipedia.org/wiki/WebSocket"),
        ("API", "Schnittstelle, über die die Seite (oder ein Skript) den Server steuert, z. B. /api/mandel/start.",
         "https://de.wikipedia.org/wiki/Programmierschnittstelle"),
        ("vcomp140.dll / OpenMP", "OpenMP ist ein Standard, mit dem C/C++-Programme Schleifen auf Threads verteilen; vcomp140.dll ist Microsofts Laufzeitbibliothek dafür und liegt dem Paket bei.",
         "https://learn.microsoft.com/de-de/cpp/parallel/openmp/openmp-in-visual-cpp"),
        ("0.0.0.0", "Server-Einstellung „auf allen Netzwerkkarten erreichbar“. Der Monitor nutzt das bewusst nicht, sondern nur 127.0.0.1.", None),
        ("JSON / CSV", "Textformate für Messdaten: JSON für strukturierte Daten (eine Datei je Messung), CSV als Tabelle, die z. B. Excel öffnen kann.",
         "https://de.wikipedia.org/wiki/JavaScript_Object_Notation"),
        ("base64", "Verfahren, Binärdaten (hier Bildkacheln) als reinen Text zu verschicken; etwa ein Drittel größer als das Original.",
         "https://de.wikipedia.org/wiki/Base64"),
        ("pip", "Paketverwaltung von Python; installiert Erweiterungen wie numba oder FastAPI.", "https://pip.pypa.io/"),
        ("winget", "Paketverwaltung von Windows; installiert Programme wie Python, .NET oder Rust per Befehlszeile.",
         "https://learn.microsoft.com/de-de/windows/package-manager/winget/"),
        ("rustup / cargo", "rustup installiert und aktualisiert Rust; cargo übersetzt Rust-Programme und lädt benötigte Bibliotheken.",
         "https://rustup.rs/"),
        ("Visual Studio Build Tools", "Microsofts Compiler für C, C++ und Assembler ohne die volle Entwicklungsumgebung; kostenlos.",
         "https://visualstudio.microsoft.com/de/downloads/"),
    ]),
    ("Ergänzungen", [
        ("DNS-Rebinding", "Angriff, bei dem eine fremde Webseite ihren Namen auf 127.0.0.1 umleitet, um aus dem Browser heraus lokale Dienste zu steuern. Der Monitor prüft deshalb bei jeder Anfrage Host und Herkunft und weist Fremdes ab.",
         "https://en.wikipedia.org/wiki/DNS_rebinding"),
        ("Fehlalarm (False Positive)", "Ein Virenscanner hält ein harmloses Programm für gefährlich, weil es sich ähnlich verhält wie Schadsoftware (z. B. unsignierte .exe, volle Auslastung aller Kerne). Siehe „Hinweis zum Virenscanner“.",
         "https://de.wikipedia.org/wiki/Falsch_positiv"),
        ("Quarantäne", "Abgeschotteter Bereich des Virenscanners für verdächtige Dateien; von dort lassen sie sich wiederherstellen.",
         "https://de.wikipedia.org/wiki/Antivirenprogramm"),
        ("SmartScreen", "Windows-Schutz, der vor unbekannten, nicht signierten Programmen warnt („Der Computer wurde durch Windows geschützt“).",
         "https://learn.microsoft.com/de-de/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/"),
        ("Digitale Signatur (Code-Signatur)", "Elektronische Unterschrift eines Herstellers an einer .exe; signierte, verbreitete Programme lösen seltener Warnungen aus. Die Programme des Kern-Monitors sind nicht signiert.",
         "https://en.wikipedia.org/wiki/Code_signing"),
        ("VirusTotal", "Kostenloser Dienst, der eine Datei mit rund 70 Virenscannern gleichzeitig prüft.", "https://www.virustotal.com/"),
        ("psutil", "Python-Bibliothek, die Auslastung, Speicher und Prozesse abfragt; liefert die Werte für die Kern-Anzeige.",
         "https://psutil.readthedocs.io/"),
        ("Prozessorgruppe", "Windows fasst höchstens 64 Threads zu einer Gruppe zusammen. Prozessoren mit mehr Threads haben mehrere Gruppen; ein Prozess läuft normalerweise nur in einer.",
         "https://learn.microsoft.com/de-de/windows/win32/procthread/processor-groups"),
        ("Scheduler", "Teil von Windows, der entscheidet, welcher Thread wann auf welchem Kern läuft (Platzierung „Windows entscheidet“).",
         "https://de.wikipedia.org/wiki/Prozess-Scheduler"),
        ("AVX-512", "Nachfolger von AVX2 mit 512-Bit-Registern (8 double gleichzeitig). Der Threadripper 3960X hat es nicht; neuere Prozessoren teils schon.",
         "https://de.wikipedia.org/wiki/AVX-512"),
        ("Vector256", ".NET-Datentyp für ein 256-Bit-Register (4 double); damit nutzt C# AVX2.",
         "https://learn.microsoft.com/de-de/dotnet/api/system.runtime.intrinsics.vector256"),
        ("x64", "64-Bit-Befehlssatz der heutigen Intel- und AMD-Prozessoren (auch x86-64 oder AMD64).", "https://de.wikipedia.org/wiki/X64"),
        ("DXGI", "Windows-Schnittstelle, über die der Monitor die vorhandenen Grafikkarten und ihren Speicher erkennt.",
         "https://learn.microsoft.com/de-de/windows/win32/direct3ddxgi/dx-graphics-dxgi"),
        ("Seepferdchental", "Bekannter Ausschnitt der Mandelbrot-Menge zwischen Hauptfläche und Periode-2-Kreis; sehr fein verästelt und daher rechenaufwendig.",
         "https://de.wikipedia.org/wiki/Mandelbrot-Menge"),
    ]),
]
# ---- English: German term -> (English term, explanation, link; None = same link as German) ----
EN = {
    "DNS-Rebinding": ("DNS rebinding", "Attack in which a foreign website points its name to 127.0.0.1 to control local services from the browser. The monitor therefore checks Host and origin of every request and rejects anything foreign.", "https://en.wikipedia.org/wiki/DNS_rebinding"),
    "Kern (Prozessorkern)": ("Core (processor core)", "Independent execution unit inside the processor. The Threadripper 3960X has 24 cores.", "https://en.wikipedia.org/wiki/Multi-core_processor"),
    "Thread (Hardware-Thread, logischer Prozessor)": ("Thread (hardware thread, logical processor)", "What Windows counts as a \"CPU\". With SMT every core offers 2 threads, i.e. 48 on the 3960X.", "https://en.wikipedia.org/wiki/Thread_(computing)"),
    "SMT (Simultaneous Multithreading, bei Intel „Hyper-Threading“)": ("SMT (simultaneous multithreading, Intel: \"Hyper-Threading\")", "One core runs two instruction streams at once and fills gaps in its execution units. Usually gains 0–30 %, not 100 %.", "https://en.wikipedia.org/wiki/Simultaneous_multithreading"),
    "CCX (Core Complex)": ("CCX (Core Complex)", "On AMD Zen processors a group of cores sharing one L3 cache; the 3960X has 8 CCXs with 3 cores each. Called \"L3 group\" in the monitor.", None),
    "Cache (L1/L2/L3)": ("Cache (L1/L2/L3)", "Fast buffer memory inside the processor. L1/L2 belong to one core, L3 is shared by the cores of a CCX.", "https://en.wikipedia.org/wiki/CPU_cache"),
    "NUMA": ("NUMA", "Non-Uniform Memory Access: on large systems memory is reached at different speeds depending on the core. The 3960X has one NUMA node.", "https://en.wikipedia.org/wiki/Non-uniform_memory_access"),
    "CPU-Affinität (Platzierung)": ("CPU affinity (placement)", "Defines on which threads a process may run. The monitor uses it to compare \"1 thread per core first\" with \"compact\".", None),
    "GPU (Grafikkarte)": ("GPU (graphics card)", "Processor with thousands of simple execution units; ideal when a huge number of identical calculations is needed (e.g. one per pixel).", "https://en.wikipedia.org/wiki/Graphics_processing_unit"),
    "Prozess": ("Process", "A running program with its own memory. Processes run independently but can exchange data only indirectly.", "https://en.wikipedia.org/wiki/Process_(computing)"),
    "Thread (Software)": ("Thread (software)", "Execution path inside a process; all threads share the memory and start much faster than processes.", "https://en.wikipedia.org/wiki/Thread_(computing)"),
    "Worker": ("Worker", "A process or thread that works through tiles. The number of workers is set in the monitor (1–48).", None),
    "Skalierung, Beschleunigung, Effizienz": ("Scaling, speedup, efficiency", "Speedup = time with 1 worker ÷ time with n workers. Efficiency = speedup ÷ n (100 % = perfect).", "https://en.wikipedia.org/wiki/Speedup"),
    "Amdahlsches Gesetz": ("Amdahl's law", "The part of a program that cannot run in parallel limits the possible speedup, no matter how many cores are used (see Pi).", "https://en.wikipedia.org/wiki/Amdahl%27s_law"),
    "Lastverteilung (dynamisch)": ("Load balancing (dynamic)", "Whoever finishes a tile fetches the next one. No core sits idle even though tiles take different amounts of time.", "https://en.wikipedia.org/wiki/Load_balancing_(computing)"),
    "Median": ("Median", "Middle value of a sorted series of measurements; less sensitive to outliers than the average. Used when several runs are made.", "https://en.wikipedia.org/wiki/Median"),
    "Heatmap": ("Heat map", "Coloured tile view: one field per thread, colour = current load.", "https://en.wikipedia.org/wiki/Heat_map"),
    "Python": ("Python", "Widely used scripting language; used here for the web server, control logic and two computation methods.", None),
    "GIL (Global Interpreter Lock)": ("GIL (Global Interpreter Lock)", "Lock in standard Python: only one thread executes Python code at a time. That is why the monitor uses processes instead of threads for Python.", None),
    "ProcessPoolExecutor": ("ProcessPoolExecutor", "Python building block that manages a pool of worker processes and distributes tasks to them.", None),
    "numba": ("numba", "Compiles selected Python functions to machine code on first call (JIT), making them about as fast as C.", None),
    "JIT (Just-in-time-Übersetzung)": ("JIT (just-in-time compilation)", "Code is compiled to machine code only while the program runs; the first call therefore takes longer.", "https://en.wikipedia.org/wiki/Just-in-time_compilation"),
    "numpy": ("numpy", "Python library for computing with whole arrays of numbers. Fast for simple array operations, but not ideal for Mandelbrot.", None),
    "OpenBLAS": ("OpenBLAS", "Math library inside numpy that starts its own threads. Limited to 1 thread per process in the monitor, otherwise every worker needs ~800 MB.", None),
    "gmpy2 / GMP": ("gmpy2 / GMP", "Library for very large numbers with any number of digits; the basis of the Pi computation.", None),
    "mpmath": ("mpmath", "Python library for arbitrary-precision arithmetic; serves as an independent cross-check of the Pi digits.", None),
    "Embedded Python": ("Embedded Python", "Official, lean Python distribution that can be shipped in a folder without installation. Included in the \"Full\" package.", None),
    "C# / .NET": ("C# / .NET", "Programming language and runtime from Microsoft; real threads, compiled to machine code at run time.", "https://learn.microsoft.com/en-us/dotnet/csharp/"),
    "Self-contained Single-File": ("Self-contained single file", ".NET program that carries the runtime inside a single .exe; runs without an installed .NET.", "https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview"),
    "Rust": ("Rust", "Modern systems language with C-like speed; its compiler prevents typical mistakes when working with threads.", None),
    "C / C++": ("C / C++", "Classic languages close to the hardware. Compiled here with the Microsoft compiler (MSVC) from Visual Studio.", "https://learn.microsoft.com/en-us/cpp/"),
    "Assembler (MASM)": ("Assembler (MASM)", "Processor instructions in readable form, written by hand. MASM is the Microsoft Macro Assembler.", "https://learn.microsoft.com/en-us/cpp/assembler/masm/microsoft-macro-assembler-reference"),
    "Compiler-Schalter /O2, /arch:AVX2, /fp:precise, /MT": ("Compiler switches /O2, /arch:AVX2, /fp:precise, /MT", "Optimise, allow AVX2 instructions, compute exactly as written (no FMA), link the runtime library statically (no extra DLLs needed).", "https://learn.microsoft.com/en-us/cpp/build/reference/compiler-options-listed-by-category"),
    "Intrinsics": ("Intrinsics", "Functions in C/C++/Rust that map directly to one processor instruction (e.g. AVX2); SIMD without assembler.", "https://learn.microsoft.com/en-us/cpp/intrinsics/compiler-intrinsics"),
    "Direct3D 11 Compute-Shader / HLSL": ("Direct3D 11 compute shader / HLSL", "Program that runs on the graphics card; written in HLSL, launched via Direct3D 11 (works with any current graphics card on Windows).", "https://learn.microsoft.com/en-us/windows/win32/direct3d11/direct3d-11-advanced-stages-compute-shader"),
    "SIMD": ("SIMD", "Single Instruction, Multiple Data: one instruction processes several numbers at once.", "https://en.wikipedia.org/wiki/Single_instruction,_multiple_data"),
    "AVX2": ("AVX2", "SIMD instruction set of current x86 processors; 256-bit registers hold 4 floating-point numbers (double), i.e. 4 pixels per instruction.", "https://en.wikipedia.org/wiki/Advanced_Vector_Extensions"),
    "FMA (Fused Multiply-Add)": ("FMA (fused multiply-add)", "Multiplication and addition in one step with a single rounding. Faster, but changes the last digit – and thus individual pixels.", None),
    "double / float": ("double / float", "Floating-point numbers with double (≈ 16 digits) or single precision (≈ 7 digits) according to IEEE 754. Gaming graphics cards are much faster with float.", "https://en.wikipedia.org/wiki/IEEE_754"),
    "bitgenau": ("Bit-identical", "Every byte of the result is identical – here: 0 pixels difference between the computation methods.", None),
    "Mandelbrot-Menge": ("Mandelbrot set", "Famous fractal: for every pixel z → z² + c is repeated until the value \"escapes\" or the maximum count is reached. Every point is independent – ideal for parallelisation.", "https://en.wikipedia.org/wiki/Mandelbrot_set"),
    "Iterationen (max_iter)": ("Iterations (max_iter)", "The maximum number of times z → z² + c is repeated. More iterations = finer edges, but more computing time (especially in the black interior).", None),
    "Kachel": ("Tile", "Rectangular part of the image (default 128 × 128 pixels), the smallest unit of work for a worker.", None),
    "Kardioide und Periode-2-Kreis": ("Cardioid and period-2 bulb", "The heart-shaped main area and the large disc to its left certainly belong to the Mandelbrot set. A short formula detects these points without iterating them up to the maximum.", "https://en.wikipedia.org/wiki/Mandelbrot_set#Main_cardioid_and_period_bulbs"),
    "„Aufwendige Kacheln zuerst“": ("\"Demanding tiles first\"", "Order in which a rough up-front estimate puts the most compute-intensive tiles first, so that no long tile is left running alone at the end.", None),
    "Chudnovsky-Formel": ("Chudnovsky formula", "Very fast converging series for Pi: about 14 new digits per term.", None),
    "Binary Splitting": ("Binary splitting", "Technique that combines the series terms pairwise into large fractions; the parts can be computed in parallel, the final division cannot.", None),
    "127.0.0.1 (localhost)": ("127.0.0.1 (localhost)", "Address of your own PC. The server listens only there and is therefore not reachable from other computers.", "https://en.wikipedia.org/wiki/Localhost"),
    "FastAPI / uvicorn": ("FastAPI / uvicorn", "Python building blocks of the web server: FastAPI describes the interfaces, uvicorn serves them.", None),
    "WebSocket": ("WebSocket", "Permanent connection between browser and server; the load values arrive through it every second without reloading.", "https://en.wikipedia.org/wiki/WebSocket"),
    "API": ("API", "Interface through which the page (or a script) controls the server, e.g. /api/mandel/start.", "https://en.wikipedia.org/wiki/API"),
    "vcomp140.dll / OpenMP": ("vcomp140.dll / OpenMP", "OpenMP is a standard that lets C/C++ programs distribute loops across threads; vcomp140.dll is Microsoft's runtime library for it and is included in the package.", "https://learn.microsoft.com/en-us/cpp/parallel/openmp/openmp-in-visual-cpp"),
    "0.0.0.0": ("0.0.0.0", "Server setting \"reachable on all network adapters\". The monitor deliberately does not use it, only 127.0.0.1.", None),
    "JSON / CSV": ("JSON / CSV", "Text formats for measurements: JSON for structured data (one file per measurement), CSV as a table that e.g. Excel can open.", "https://en.wikipedia.org/wiki/JSON"),
    "base64": ("base64", "Method to send binary data (here image tiles) as plain text; about one third larger than the original.", "https://en.wikipedia.org/wiki/Base64"),
    "pip": ("pip", "Python's package manager; installs extensions such as numba or FastAPI.", None),
    "winget": ("winget", "Windows package manager; installs programs such as Python, .NET or Rust from the command line.", "https://learn.microsoft.com/en-us/windows/package-manager/winget/"),
    "rustup / cargo": ("rustup / cargo", "rustup installs and updates Rust; cargo builds Rust programs and downloads the libraries they need.", None),
    "Visual Studio Build Tools": ("Visual Studio Build Tools", "Microsoft's compilers for C, C++ and assembler without the full development environment; free of charge.", "https://visualstudio.microsoft.com/downloads/"),
    "Fehlalarm (False Positive)": ("False positive", "Antivirus software considers a harmless program dangerous because it behaves similarly to malware (e.g. unsigned .exe, full load on all cores). See \"Note on antivirus software\".", "https://en.wikipedia.org/wiki/False_positives_and_false_negatives"),
    "Quarantäne": ("Quarantine", "Isolated area of the antivirus software for suspicious files; they can be restored from there.", "https://en.wikipedia.org/wiki/Antivirus_software"),
    "SmartScreen": ("SmartScreen", "Windows protection that warns about unknown, unsigned programs (\"Windows protected your PC\").", "https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/"),
    "Digitale Signatur (Code-Signatur)": ("Digital signature (code signing)", "Electronic signature of a publisher on an .exe; signed, widely used programs trigger warnings less often. The programs of Core Monitor are not signed.", None),
    "VirusTotal": ("VirusTotal", "Free service that checks a file with about 70 antivirus engines at once.", None),
    "psutil": ("psutil", "Python library that queries load, memory and processes; supplies the values for the core display.", None),
    "Prozessorgruppe": ("Processor group", "Windows combines at most 64 threads into one group. Processors with more threads have several groups; a process normally runs in only one.", "https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups"),
    "Scheduler": ("Scheduler", "Part of Windows that decides which thread runs on which core and when (placement \"Windows decides\").", "https://en.wikipedia.org/wiki/Scheduling_(computing)"),
    "AVX-512": ("AVX-512", "Successor of AVX2 with 512-bit registers (8 doubles at once). The Threadripper 3960X does not have it; some newer processors do.", "https://en.wikipedia.org/wiki/AVX-512"),
    "Vector256": ("Vector256", ".NET data type for a 256-bit register (4 doubles); this is how C# uses AVX2.", "https://learn.microsoft.com/en-us/dotnet/api/system.runtime.intrinsics.vector256"),
    "x64": ("x64", "64-bit instruction set of today's Intel and AMD processors (also called x86-64 or AMD64).", "https://en.wikipedia.org/wiki/X86-64"),
    "DXGI": ("DXGI", "Windows interface the monitor uses to detect the installed graphics cards and their memory.", "https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/dx-graphics-dxgi"),
    "Seepferdchental": ("Seahorse valley", "Well-known region of the Mandelbrot set between the main cardioid and the period-2 bulb; very finely branched and therefore compute-intensive.", "https://en.wikipedia.org/wiki/Mandelbrot_set"),
}

ROOT = Path(__file__).resolve().parent.parent
TEXT = {
    "de": {"title": "Begriffe kurz erklärt", "intro": "Alphabetisch, mit Link zu einer weiterführenden Quelle.",
           "more": "mehr", "count": "Fachbegriffe, mit Links zum Weiterlesen", "search": "Begriff suchen, z. B. SIMD oder Kardioide",
           "none": "Kein Begriff gefunden."},
    "en": {"title": "Glossary", "intro": "Alphabetical, with a link to further reading.",
           "more": "more", "count": "technical terms, with links for further reading", "search": "Search a term, e.g. SIMD or cardioid",
           "none": "No term found."},
}


def items(lang: str) -> list[tuple[str, str, str | None]]:
    """All terms of one language, sorted alphabetically: (term, explanation, link)."""
    out = []
    for _, group in G:
        for name, desc, url in group:
            if lang == "en":
                n, d, u = EN[name]
                name, desc, url = n, d, (u or url)
            out.append((name, desc, url))
    return sorted(out, key=lambda i: i[0].lstrip("„\".0").casefold())


def anchor(name):
    """Anchor per term, e.g. g-simd, g-c-net."""
    return "g-" + "-".join("".join(ch if ch.isalnum() else " " for ch in name.casefold()).split())


def letter(name):
    c = name.lstrip("„\".")[:1].upper()
    return c if c.isalpha() else "0–9"


def check():
    """Fetch every link of both languages and report the broken ones."""
    bad = 0
    urls = sorted({u for lang in ("de", "en") for _, _, u in items(lang) if u})
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            code = urllib.request.urlopen(req, timeout=20).status
        except Exception as e:
            code = getattr(e, "code", str(e)[:60])
        if code != 200:
            bad += 1
            print(code, url)
    print(f"links: {len(urls)}, broken: {bad}")


def markdown(lang: str) -> str:
    t = TEXT[lang]
    out = [f"## {t['title']}", "", t["intro"], ""]
    for name, desc, url in items(lang):
        out.append(f"- **{name}:** {desc}" + (f" <{url}>" if url else ""))
    return "\n".join(out) + "\n"


def html_section(lang: str) -> str:
    t = TEXT[lang]
    h = [f'<h2 class="pb">10. {t["title"]}</h2>', f"<p>{t['intro']}</p>", '<table class="gloss">']
    for name, desc, url in items(lang):
        link = f'<br><a href="{html.escape(url)}">{html.escape(url)}</a>' if url else ""
        h.append(f"  <tr><td>{html.escape(name)}</td><td>{html.escape(desc)}{link}</td></tr>")
    h.append("</table>")
    return "\n".join(h) + "\n"


def readme():
    """Replace the glossary at the end of README.md (English) and README.de.md (German)."""
    for fname, lang in (("README.md", "en"), ("README.de.md", "de")):
        md = ROOT / fname
        if not md.exists():
            continue
        t = md.read_text(encoding="utf-8")
        head = f"## {TEXT[lang]['title']}\n"
        if head in t:
            t = t[:t.index(head)]
        md.write_text(t.rstrip() + "\n\n" + markdown(lang), encoding="utf-8")


def report(path: str, lang: str):
    """Replace chapter 10 (glossary) in the HTML source of the project report."""
    p = Path(path)
    r = p.read_text(encoding="utf-8")
    m = r.find('<h2 class="pb">10. ')
    if m >= 0:
        r = r[:m] + "</body>" + r.split("</body>", 1)[1]
    css = ("  table.gloss td:first-child { width: 33%; font-weight: 600; }\n"
           "  table.gloss { break-inside: auto; } table.gloss tr { break-inside: avoid; }\n"
           "  a { color: #2563eb; text-decoration: none; word-break: break-all; font-size: 8.3pt; }\n")
    if "table.gloss" not in r:
        r = r.replace("</style>", css + "</style>", 1)
    p.write_text(r.replace("</body>", html_section(lang) + "</body>", 1), encoding="utf-8")


def web():
    """Insert the collapsible glossary (both languages, shown via data-l) into static/index.html."""
    parts = []
    for lang in ("de", "en"):
        t, its = TEXT[lang], items(lang)
        letters, rows = [], []
        for name, desc, url in its:
            a = f"{anchor(name)}-{lang}"
            if letter(name) not in [l for l, _ in letters]:
                letters.append((letter(name), a))
            link = f' <a href="{html.escape(url)}" target="_blank" rel="noopener">{t["more"]} ↗</a>' if url else ""
            rows.append(f'      <dt id="{a}">{html.escape(name)}</dt><dd>{html.escape(desc)}{link}</dd>')
        nav = " ".join(f'<a href="#{a}">{l}</a>' for l, a in letters)
        parts.append(
            f'  <div data-l="{lang}">\n'
            f'    <div class="gloss-head">\n'
            f'      <input type="search" class="gloss-filter" placeholder="{html.escape(t["search"])}" autocomplete="off">\n'
            f'      <nav class="gloss-nav">{nav}</nav>\n'
            f'    </div>\n'
            f'    <dl class="gloss-list">\n' + "\n".join(rows) + "\n    </dl>\n"
            f'    <div class="gloss-none muted small" hidden>{t["none"]}</div>\n'
            f'  </div>\n')
    n = len(items("de"))
    block = ("  <!-- GLOSSAR-START: generated by tools/glossar.py – edit there, not here -->\n"
             '  <details class="panel system gloss" id="gloss-box">\n'
             f'    <summary><b><span data-l="de">{TEXT["de"]["title"]}</span><span data-l="en">{TEXT["en"]["title"]}</span></b> · '
             f'<span class="muted">{n} <span data-l="de">{TEXT["de"]["count"]}</span><span data-l="en">{TEXT["en"]["count"]}</span></span></summary>\n'
             + "".join(parts) +
             "  </details>\n  <!-- GLOSSAR-ENDE -->\n")
    p = ROOT / "static" / "index.html"
    t = p.read_text(encoding="utf-8")
    a = t.index("  <!-- GLOSSAR-START")
    b = t.index("<!-- GLOSSAR-ENDE -->") + len("<!-- GLOSSAR-ENDE -->\n")
    p.write_text(t[:a] + block + t[b:], encoding="utf-8")


if __name__ == "__main__":
    missing = [name for _, g in G for name, _, _ in g if name not in EN]
    if missing:
        raise SystemExit(f"missing English entries: {missing}")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        check()
    elif cmd == "report":
        report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "de")
        print("report updated")
    else:
        readme()
        web()
        print(f"README files and web page updated ({len(items('de'))} terms per language)")
