"""Privacy check for the distribution packages.

Searches all files in a folder – text and binary files, as ASCII/Latin-1 and UTF-16 – as well as the text of
PDF files for information that reveals this PC or its user. The search patterns are determined by the caller at
runtime (user name/profile path, project path, computer name, LAN addresses, MAC addresses).

Usage: python privacy_check.py <folder> <pattern> [<pattern> …]
Exit code: 0 = clean, 1 = hits found (the list is printed).
"""
import re
import sys
from pathlib import Path

folder = Path(sys.argv[1])
patterns = sorted({p for p in sys.argv[2:] if p and len(p) >= 4}, key=len, reverse=True)
regex = re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)
hits = []

for f in folder.rglob("*"):
    if not f.is_file():
        continue
    data = f.read_bytes()
    texts = [data.decode("latin-1"), data.decode("utf-16-le", errors="ignore")]
    if f.suffix.lower() == ".pdf":   # PDF content is compressed -> extract the text
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(f))
            texts.append("\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc))))
            texts.append(" ".join(str(v) for v in doc.get_metadata_dict().values()))
        except ImportError:
            print(f"Note: pypdfium2 missing, PDF text of {f.name} not checked")
    for t in texts:
        m = regex.search(t)
        if m:
            ctx = "".join(ch if ch.isprintable() else "·" for ch in t[max(0, m.start() - 40):m.end() + 40])
            hits.append(f"{f.relative_to(folder)}: …{ctx}…")
            break

print(f"Privacy check: {sum(1 for _ in folder.rglob('*'))} entries, {len(patterns)} search patterns, {len(hits)} hits")
for h in hits:
    print("  HIT", h)
sys.exit(1 if hits else 0)
