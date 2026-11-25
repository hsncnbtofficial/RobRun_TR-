"""Split untranslated, de-duplicated English texts into batch files for translation.

work/batch_NNN_en.json : {"<n>": {"en": text, "key": first key using it}}
work/units.json        : {"<n>": [list of "Table::key" that use this text]}
Translations go to work/batch_NNN_tr.json : {"<n>": "türkçe"}
"""
import json
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
BATCH = 150

en = json.loads((ROOT / "data" / "strings_en.json").read_text(encoding="utf-8"))
tr = json.loads((ROOT / "data" / "strings_tr.json").read_text(encoding="utf-8"))

units = OrderedDict()           # english text -> list of keys
for table, entries in en.items():
    for _, e in entries.items():
        key = f"{table}::{e['key']}"
        if key in tr:
            continue
        units.setdefault(e["en"], []).append(key)

WORK.mkdir(exist_ok=True)
texts = list(units)
skip = [t for t in texts if not re.search(r"[A-Za-z]", t)]          # numbers/symbols only
texts = [t for t in texts if t not in skip]
meta = {}
for b in range(0, len(texts), BATCH):
    chunk = {}
    for n, t in enumerate(texts[b:b + BATCH], start=b):
        chunk[str(n)] = {"key": units[t][0].split("::", 1)[1], "en": t}
        meta[str(n)] = units[t]
    (WORK / f"batch_{b // BATCH:03d}_en.json").write_text(json.dumps(chunk, ensure_ascii=False, indent=0), encoding="utf-8")
(WORK / "units.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
print(f"satır: {sum(len(v) for v in units.values())}, benzersiz: {len(units)}, çevrilecek: {len(texts)}, "
      f"sembol (atlandı): {len(skip)}, parça: {(len(texts) + BATCH - 1) // BATCH}, karakter: {sum(map(len, texts))}")
