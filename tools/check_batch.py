"""Validate a translated batch: all ids present, tags/placeholders intact.

Input: work/batch_NNN_tr.txt with lines  n|turkish   (\\n for newlines)
Writes work/batch_NNN_tr.json when valid entries exist; prints problems.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "robrun_tr"))
from build import problems  # noqa: E402

WORK = ROOT / "work"
sys.stdout.reconfigure(encoding="utf-8")
for arg in sys.argv[1:]:
    b = int(arg)
    en = json.loads((WORK / f"batch_{b:03d}_en.json").read_text(encoding="utf-8"))
    tr = {}
    for line in (WORK / f"batch_{b:03d}_tr.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or "|" not in line:
            continue
        n, text = line.split("|", 1)
        tr[n.strip()] = text.replace("\\n", "\n")
    missing = [n for n in en if n not in tr]
    bad = {n: problems(en[n]["en"], t) for n, t in tr.items() if n in en and problems(en[n]["en"], t)}
    extra = [n for n in tr if n not in en]
    good = {n: t for n, t in tr.items() if n in en and n not in bad}
    (WORK / f"batch_{b:03d}_tr.json").write_text(json.dumps(good, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"batch {b:03d}: ok {len(good)}/{len(en)}  eksik {len(missing)}  hatalı {len(bad)}  fazla {len(extra)}")
    for n in missing[:20]:
        print(f"   EKSİK {n}: {en[n]['en'][:70]!r}")
    for n, e in bad.items():
        print(f"   HATA {n} ({', '.join(e)}): EN={en[n]['en']!r}\n        TR={tr[n]!r}")
