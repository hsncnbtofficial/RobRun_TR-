"""Re-open out/fonts_tr.bundle from disk and render the preview from it (round-trip check)."""
import sys
from pathlib import Path

import UnityPy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "robrun_tr"))
from fonts import Font, preview  # noqa: E402

env = UnityPy.load(str(ROOT / "out" / "fonts_tr.bundle"))
by_id = {o.path_id: o for o in env.objects}
fonts = {}
for obj in env.objects:
    if obj.type.name != "MonoBehaviour":
        continue
    try:
        t = obj.read_typetree()
    except Exception:
        continue
    if "m_CharacterTable" in t and t.get("m_AtlasTextures"):
        f = Font(obj, t, by_id[t["m_AtlasTextures"][0]["m_PathID"]])
        fonts[f.name] = f
        tex = f.tex_obj.read()
        tr = "".join(c for c in "İıŞşĞğ" if f.has(c))
        print(f"{f.name:38} atlas={f.W}x{f.H} m_AtlasHeight={t['m_AtlasHeight']} fmt={tex.m_TextureFormat} türkçe={tr or '-'}")
preview(fonts, ROOT / "out" / "fonts_preview_roundtrip.png")
print("ok")
