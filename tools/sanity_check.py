"""Heuristic check for misaligned translations (line shifts): length ratio and digits."""
import json
import re
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent / "work"
sys.stdout.reconfigure(encoding="utf-8")
strip = lambda s: re.sub(r"<[^>]*>|\{[^{}]*\}", "", s)
flag = 0
for f in sorted(WORK.glob("batch_*_tr.json")):
    b = f.name[6:9]
    en = json.loads((WORK / f"batch_{b}_en.json").read_text(encoding="utf-8"))
    tr = json.loads(f.read_text(encoding="utf-8"))
    for n, t in tr.items():
        e = en[n]["en"]
        le, lt = len(strip(e)), len(strip(t))
        digits_e = sorted(re.findall(r"\d+", strip(e)))
        digits_t = sorted(re.findall(r"\d+", strip(t)))
        bad = []
        if le >= 25 and not (0.5 <= lt / max(le, 1) <= 2.0):
            bad.append(f"oran {lt / le:.2f}")
        if digits_e and digits_e != digits_t:
            bad.append(f"sayı {digits_e}->{digits_t}")
        if bad:
            flag += 1
            print(f"[{b}:{n}] {', '.join(bad)}\n   EN: {e[:110]!r}\n   TR: {t[:110]!r}")
print("şüpheli:", flag)
