"""Print a batch compactly: n|key|english (newlines shown as \\n)."""
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent / "work"
b = int(sys.argv[1])
data = json.loads((WORK / f"batch_{b:03d}_en.json").read_text(encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
for n, v in data.items():
    print(f"{n}|{v['key']}|{v['en']!s}".replace("\n", "\\n"))
