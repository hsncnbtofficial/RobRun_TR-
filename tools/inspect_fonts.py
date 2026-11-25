"""Inspect TMP font assets in inbuild bundle: atlas size, padding, glyph rects of key letters."""
import sys
from pathlib import Path

import UnityPy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "robrun_tr"))
from common import FONT_BUNDLE, bundle_dir, find_game_dir  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "out" / "font_inspect"
OUT.mkdir(parents=True, exist_ok=True)
env = UnityPy.load(str(bundle_dir(find_game_dir()) / FONT_BUNDLE))
by_id = {o.path_id: o for o in env.objects}

for obj in env.objects:
    if obj.type.name != "MonoBehaviour":
        continue
    try:
        t = obj.read_typetree()
    except Exception:
        continue
    if "m_CharacterTable" not in t:
        continue
    print(f"\n=== {t['m_Name']}  (path_id {obj.path_id})")
    fi = t.get("m_FaceInfo", {})
    print("  face:", {k: fi.get(k) for k in ("m_PointSize", "m_Scale", "m_LineHeight", "m_AscentLine", "m_CapLine", "m_MeanLine", "m_Baseline", "m_DescentLine")})
    print("  atlas:", t.get("m_AtlasWidth"), "x", t.get("m_AtlasHeight"), "padding", t.get("m_AtlasPadding"),
          "renderMode", t.get("m_AtlasRenderMode"), "textures", [a["m_PathID"] for a in t.get("m_AtlasTextures", [])])
    print("  fallbacks:", [f["m_PathID"] for f in t.get("m_FallbackFontAssetTable", [])])
    glyphs = {g["m_Index"]: g for g in t["m_GlyphTable"]}
    chars = {c["m_Unicode"]: c["m_GlyphIndex"] for c in t["m_CharacterTable"]}
    print("  glyph keys:", list(t["m_GlyphTable"][0].keys()))
    for ch in "IiSsGgÇçÖöÜüHn":
        gi = chars.get(ord(ch))
        if gi is None:
            continue
        g = glyphs[gi]
        print(f"   {ch}: idx={gi} metrics={g['m_Metrics']} rect={g['m_GlyphRect']} atlas={g.get('m_AtlasIndex')}")
    for a in t.get("m_AtlasTextures", []):
        tex = by_id.get(a["m_PathID"])
        if tex is not None:
            img = tex.read().image
            img.save(OUT / f"{t['m_Name']}_{a['m_PathID']}.png")
            print("  saved atlas", img.size, img.mode)
