"""Merge work/batch_*_tr.json into data/strings_tr.json ("Table::key" -> Turkish).

Literal escape sequences such as "\\u24e6" in the English source are restored in the
Turkish text (the game unescapes them itself), so both use the exact same form.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
TR_JSON = ROOT / "data" / "strings_tr.json"

units = json.loads((WORK / "units.json").read_text(encoding="utf-8"))
tr_all = json.loads(TR_JSON.read_text(encoding="utf-8")) if TR_JSON.exists() else {}
added = 0
for f in sorted(WORK.glob("batch_*_tr.json")):
    en = json.loads((WORK / f.name.replace("_tr.json", "_en.json")).read_text(encoding="utf-8"))
    for n, text in json.loads(f.read_text(encoding="utf-8")).items():
        for esc in re.findall(r"\\u[0-9a-fA-F]{4}", en[n]["en"]):
            text = text.replace(chr(int(esc[2:], 16)), esc)
        for key in units[n]:
            if key not in tr_all:
                added += 1
            tr_all[key] = text
TR_JSON.write_text(json.dumps(tr_all, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"toplam çeviri: {len(tr_all)} (yeni: {added}) -> {TR_JSON}")
