"""Add Turkish glyphs (İ ı Ş ş Ğ ğ) to the game's TextMeshPro SDF fonts.

The new glyphs are composed from glyphs that already exist in the same font, so they
match the game's style exactly:
    İ = I + dot of i        ı = i without its dot
    Ş = S + cedilla of Ç    ş = s + cedilla of ç
    Ğ = G + breve of Й      ğ = g + breve of й   (Cyrillic short-i carries a breve)
Missing source glyphs are borrowed (scaled) from a sibling "donor" font.

Pipeline per glyph: upsample SDF crops -> binary hi-res masks -> compose -> exact signed
distance (EDT) -> calibrated SDF alpha -> downsample -> pack into a free atlas spot.
Output: out/fonts_tr.bundle (+ out/fonts_preview.png)
"""
import argparse
import math

import numpy as np
import UnityPy
from PIL import Image, ImageDraw
from scipy import ndimage

from common import FONT_BUNDLE, OUT_DIR, bundle_dir, find_game_dir

UP = 8                                   # hi-res supersampling factor
EXTEND = 256                             # rows added on top of a full atlas
BASE_OF = {"İ": "I", "ı": "i", "Ş": "S", "ş": "s", "Ğ": "G", "ğ": "g"}   # composed glyphs
DONOR_COPY = "ÇçÖöÜüÂâÎîÛû"              # copied whole from a donor font when missing
TARGETS = DONOR_COPY + "".join(BASE_OF)
FONT_OUT = OUT_DIR / "fonts_tr.bundle"
PREVIEW_OUT = OUT_DIR / "fonts_preview.png"
DONORS = {
    "TT_Bluescreens SDF Outline": ["TT_Bluescreens SDF"],
    "RobotoBoldCondensedOutline": ["RobotoBoldCondensed"],
    "LibertinusSerifDisplay-Regular SDF": ["RobotoBoldCondensed"],
}
SKIP = {"IconsFont"}


class Layer:
    """A binary hi-res mask placed in point space (x right, y up; origin = pen/baseline)."""

    def __init__(self, mask, left, top):
        self.mask, self.left, self.top = mask, left, top      # left/top edge of mask, in pt

    @property
    def bbox(self):  # ink bbox (l, t, r, b) in pt
        ys, xs = np.nonzero(self.mask)
        return (self.left + xs.min() / UP, self.top - ys.min() / UP,
                self.left + (xs.max() + 1) / UP, self.top - (ys.max() + 1) / UP)

    def cx(self):
        l, _, r, _ = self.bbox
        return (l + r) / 2

    def shifted(self, dx, dy):
        return Layer(self.mask, self.left + dx, self.top + dy)

    def components(self):
        lab, n = ndimage.label(self.mask)
        out = []
        for i in range(1, n + 1):
            m = lab == i
            ys, xs = np.nonzero(m)
            sub = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            out.append(Layer(sub, self.left + xs.min() / UP, self.top - ys.min() / UP))
        return out


def union(layers):
    l = min(x.left for x in layers)
    t = max(x.top for x in layers)
    r = max(x.left + x.mask.shape[1] / UP for x in layers)
    b = min(x.top - x.mask.shape[0] / UP for x in layers)
    W, H = int(math.ceil((r - l) * UP)) + 1, int(math.ceil((t - b) * UP)) + 1
    canvas = np.zeros((H, W), bool)
    for x in layers:
        ox, oy = int(round((x.left - l) * UP)), int(round((t - x.top) * UP))
        h, w = x.mask.shape
        canvas[oy:oy + h, ox:ox + w] |= x.mask
    return Layer(canvas, l, t)


def difference(a, b, grow=1.0):
    """Ink of a that is not (dilated) ink of b."""
    u = union([a, b])
    A = union([a, Layer(np.zeros((1, 1), bool), u.left, u.top)]).mask
    B = union([b, Layer(np.zeros((1, 1), bool), u.left, u.top)]).mask
    hh, ww = max(A.shape[0], B.shape[0]), max(A.shape[1], B.shape[1])
    A = np.pad(A, ((0, hh - A.shape[0]), (0, ww - A.shape[1])))
    B = np.pad(B, ((0, hh - B.shape[0]), (0, ww - B.shape[1])))
    B = ndimage.binary_dilation(B, iterations=max(1, int(grow * UP)))
    return Layer(A & ~B, u.left, u.top)


class Font:
    def __init__(self, obj, tree, tex_obj):
        self.obj, self.t, self.tex_obj = obj, tree, tex_obj
        self.name = tree["m_Name"]
        self.pad = tree["m_AtlasPadding"]
        self.size = tree["m_FaceInfo"]["m_PointSize"]
        self.atlas = np.array(tex_obj.read().image.convert("RGBA"))[..., 3].astype(np.float32)
        self.H, self.W = self.atlas.shape
        self.glyphs = {g["m_Index"]: g for g in tree["m_GlyphTable"]}
        self.chars = {c["m_Unicode"]: c["m_GlyphIndex"] for c in tree["m_CharacterTable"]}
        self.k = None

    def has(self, ch):
        return ord(ch) in self.chars

    def crop(self, g):
        r, p = g["m_GlyphRect"], self.pad
        top = self.H - (r["m_Y"] + r["m_Height"])
        y0, x0 = top - p, r["m_X"] - p
        h, w = r["m_Height"] + 2 * p, r["m_Width"] + 2 * p
        out = np.zeros((h, w), np.float32)
        ys, xs = slice(max(y0, 0), min(y0 + h, self.H)), slice(max(x0, 0), min(x0 + w, self.W))
        out[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] = self.atlas[ys, xs]
        return out

    def layer(self, ch, scale=1.0):
        """Hi-res mask of a glyph, in this font's pt space times `scale`."""
        g = self.glyphs[self.chars[ord(ch)]]
        sdf = self.crop(g)
        h, w = sdf.shape
        f = UP * scale
        H, W = int(round(h * f)), int(round(w * f))
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        hi = ndimage.map_coordinates(sdf, [(yy + 0.5) / f - 0.5, (xx + 0.5) / f - 0.5], order=1, mode="nearest")
        m = g["m_Metrics"]
        left = (m["m_HorizontalBearingX"] - self.pad) * scale
        top = (m["m_HorizontalBearingY"] + self.pad) * scale
        return Layer(hi >= 127.5, left, top)

    def calibrate(self):
        """Fit alpha = 127.5 + k * signed_distance_px using an existing glyph."""
        ch = "H" if self.has("H") else "I"
        g = self.glyphs[self.chars[ord(ch)]]
        sdf = self.crop(g)
        lay = self.layer(ch)
        sd = signed_distance(lay.mask)
        sd = sd[:sdf.shape[0] * UP, :sdf.shape[1] * UP]
        sd = sd.reshape(sdf.shape[0], UP, sdf.shape[1], UP).mean(axis=(1, 3))
        sel = (sdf > 15) & (sdf < 240)
        self.k = float(((sdf[sel] - 127.5) * sd[sel]).sum() / (sd[sel] ** 2).sum())


def signed_distance(mask):
    """Signed distance in atlas pixels (inside positive)."""
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    return (inside - outside) / UP


def source(fonts, font, ch):
    """Get (font, scale) able to supply glyph `ch` for `font` (itself or a donor)."""
    if font.has(ch):
        return font, 1.0
    for d in DONORS.get(font.name, []):
        if d in fonts and fonts[d].has(ch):
            return fonts[d], font.size / fonts[d].size
    return None, None


def accent(fonts, font, composite, base, where):
    """Extract the mark from `composite` minus `base` (e.g. Ç - C), in `font`'s pt space."""
    f, s = source(fonts, font, composite)
    if f is None or not f.has(base):
        return None, None
    comp, b = f.layer(composite, s), f.layer(base, s)
    parts = [p for p in difference(comp, b).components() if p.mask.sum() > 0.02 * comp.mask.sum()]
    _, bt, _, bb = b.bbox
    if where == "below":
        parts = [p for p in parts if (p.bbox[1] + p.bbox[3]) / 2 < bb + 0.25 * (bt - bb)]
    else:
        parts = [p for p in parts if (p.bbox[1] + p.bbox[3]) / 2 > bt - 0.1 * (bt - bb)]
    if not parts:
        return None, None
    return union(parts), b


def compose(fonts, font, target):
    """Return a Layer for the new glyph, or None if this font can't support it."""
    if target not in BASE_OF:                                         # whole glyph from a donor font
        f, s = source(fonts, font, target)
        return None if f is None or f is font else f.layer(target, s)
    base = BASE_OF[target]
    if not font.has(base):
        return None
    B = font.layer(base)
    _, bt, _, bb = B.bbox
    if target == "ı":
        comps = sorted(B.components(), key=lambda c: c.bbox[1])
        return union(comps[:-1]) if len(comps) > 1 else None          # drop the top-most part (dot)
    if target == "İ":
        f, s = source(fonts, font, "i")
        if f is None:
            return None
        comps = sorted(f.layer("i", s).components(), key=lambda c: c.bbox[1])
        if len(comps) < 2:
            return None
        dot, stem = comps[-1], union(comps[:-1])
        gap = dot.bbox[3] - stem.bbox[1]
        d = dot.shifted(B.cx() - dot.cx(), (bt + gap) - dot.bbox[3])
        return union([B, d])
    if target in "Şş":
        ced, ref = accent(fonts, font, "Ç" if target == "Ş" else "ç", "C" if target == "Ş" else "c", "below")
        if ced is None:
            return None
        d = ced.shifted(B.cx() - ref.cx(), bb - ref.bbox[3])
        return union([B, d])
    if target in "Ğğ":
        brv, ref = accent(fonts, font, "Й" if target == "Ğ" else "й", "И" if target == "Ğ" else "и", "above")
        if brv is None:
            return None
        d = brv.shifted(B.cx() - brv.cx(), bt - ref.bbox[1])
        return union([B, d])


def render_sdf(font, lay):
    """Turn a composed hi-res layer into an SDF crop aligned to the atlas pixel grid."""
    l, t, r, b = lay.bbox
    w, h = int(math.ceil(r - l)), int(math.ceil(t - b))
    p = font.pad
    W, H = (w + 2 * p) * UP, (h + 2 * p) * UP
    canvas = np.zeros((H, W), bool)
    ox, oy = int(round((lay.left - (l - p)) * UP)), int(round(((t + p) - lay.top) * UP))
    mh, mw = lay.mask.shape
    sy, sx = max(0, -oy), max(0, -ox)
    ey, ex = min(mh, H - oy), min(mw, W - ox)
    canvas[oy + sy:oy + ey, ox + sx:ox + ex] = lay.mask[sy:ey, sx:ex]
    sd = signed_distance(canvas).reshape(h + 2 * p, UP, w + 2 * p, UP).mean(axis=(1, 3))
    alpha = np.clip(127.5 + font.k * sd, 0, 255)
    return alpha, (l, t, w, h)


def find_free(font, occ, h, w):
    """Top-left (y, x) of a free h*w block in the atlas (no glyph rect, no ink)."""
    busy = (occ | (font.atlas > 0)).astype(np.int32)
    ii = np.pad(busy.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    H, W = busy.shape
    sums = ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]
    ys, xs = np.nonzero(sums[:H - h + 1, :W - w + 1] == 0)
    if len(ys) == 0:
        return None
    i = np.lexsort((xs, ys))[0]
    return int(ys[i]), int(xs[i])


def patch_font(fonts, font):
    font.calibrate()
    occ = np.zeros_like(font.atlas, bool)
    for g in font.glyphs.values():
        r, p = g["m_GlyphRect"], font.pad + 1
        top = font.H - (r["m_Y"] + r["m_Height"])
        occ[max(top - p, 0):top + r["m_Height"] + p, max(r["m_X"] - p, 0):r["m_X"] + r["m_Width"] + p] = True
    next_index = max(font.glyphs) + 1
    added = []
    for ch in TARGETS:
        if font.has(ch):
            continue
        lay = compose(fonts, font, ch)
        if lay is None:
            continue
        alpha, (l, t, w, h) = render_sdf(font, lay)
        spot = find_free(font, occ, alpha.shape[0] + 2, alpha.shape[1] + 2)
        if spot is None:
            # Grow the atlas upward. Glyph rects are measured from the texture bottom,
            # so existing glyphs keep their coordinates.
            font.atlas = np.vstack([np.zeros((EXTEND, font.W), np.float32), font.atlas])
            occ = np.vstack([np.zeros((EXTEND, font.W), bool), occ])
            font.H += EXTEND
            font.t["m_AtlasHeight"] = font.H
            spot = find_free(font, occ, alpha.shape[0] + 2, alpha.shape[1] + 2)
        if spot is None:
            print(f"   ! {ch}: atlasta yer yok")
            continue
        y, x = spot[0] + 1, spot[1] + 1
        font.atlas[y:y + alpha.shape[0], x:x + alpha.shape[1]] = alpha
        occ[y - 1:y + alpha.shape[0] + 1, x - 1:x + alpha.shape[1] + 1] = True
        if ch in BASE_OF:
            advance = font.glyphs[font.chars[ord(BASE_OF[ch])]]["m_Metrics"]["m_HorizontalAdvance"]
        else:
            df, ds = source(fonts, font, ch)
            advance = df.glyphs[df.chars[ord(ch)]]["m_Metrics"]["m_HorizontalAdvance"] * ds
        rect ={"m_X": x + font.pad, "m_Y": font.H - (y + font.pad + h), "m_Width": w, "m_Height": h}
        glyph = {"m_Index": next_index,
                 "m_Metrics": {"m_Width": float(w), "m_Height": float(h), "m_HorizontalBearingX": float(l),
                               "m_HorizontalBearingY": float(t),
                               "m_HorizontalAdvance": float(advance)},
                 "m_GlyphRect": rect, "m_Scale": 1.0, "m_AtlasIndex": 0, "m_ClassDefinitionType": 0}
        font.t["m_GlyphTable"].append(glyph)
        font.t["m_CharacterTable"].append({"m_ElementType": 1, "m_Unicode": ord(ch), "m_GlyphIndex": next_index, "m_Scale": 1.0})
        font.t["m_UsedGlyphRects"].append({"m_X": x, "m_Y": font.H - (y + alpha.shape[0]),
                                           "m_Width": alpha.shape[1], "m_Height": alpha.shape[0]})
        font.glyphs[next_index] = glyph
        font.chars[ord(ch)] = next_index
        next_index += 1
        added.append(ch)
    return added


def preview(fonts, path):
    """Render a sample line per font with the patched atlases (simple SDF renderer)."""
    text = "İSTANBUL ŞAHİN ÇATIŞMA ÖDÜL ışığı GRAPHİCS • Iı Şş Ğğ İi Çç Öö Üü Ââ Îî"
    rows = []
    for f in fonts.values():
        if f.name in SKIP:
            continue
        scale = 48 / f.size
        img = Image.new("L", (1900, 80), 0)
        pen = 10.0
        for ch in text:
            gi = f.chars.get(ord(ch))
            if gi is None:
                pen += 20
                continue
            g = f.glyphs[gi]
            m, r = g["m_Metrics"], g["m_GlyphRect"]
            crop = f.crop(g)[f.pad:f.pad + r["m_Height"], f.pad:f.pad + r["m_Width"]]
            if crop.size:
                cov = np.clip((crop - 127.5) / 20 + 0.5, 0, 1) * 255
                gw, gh = max(1, int(m["m_Width"] * scale)), max(1, int(m["m_Height"] * scale))
                gimg = Image.fromarray(cov.astype(np.uint8)).resize((gw, gh), Image.LANCZOS)
                img.paste(gimg, (int(pen + m["m_HorizontalBearingX"] * scale), int(60 - m["m_HorizontalBearingY"] * scale)), gimg)
            pen += m["m_HorizontalAdvance"] * scale
        ImageDraw.Draw(img).text((1700, 5), f.name[:22], fill=120)
        rows.append(img)
    out = Image.new("L", (1900, 80 * len(rows)), 0)
    for i, r in enumerate(rows):
        out.paste(r, (0, 80 * i))
    out.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    args = ap.parse_args(argv)
    env = UnityPy.load(str(bundle_dir(find_game_dir(args.game)) / FONT_BUNDLE))
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
            fonts[t["m_Name"]] = Font(obj, t, by_id[t["m_AtlasTextures"][0]["m_PathID"]])

    for f in fonts.values():
        if f.name in SKIP:
            continue
        added = patch_font(fonts, f)
        print(f"  {f.name:38} eklendi: {''.join(added) or '-'}  (k={f.k:.1f})")

    # Materials store the atlas size (_TextureHeight) for underlay/bevel offsets.
    grown = {f.tex_obj.path_id: f.H for f in fonts.values() if f.name not in SKIP}
    mats = 0
    for obj in env.objects:
        if obj.type.name != "Material":
            continue
        mt = obj.read_typetree()
        props = mt["m_SavedProperties"]
        tex_ids = [v["m_Texture"]["m_PathID"] for k, v in props["m_TexEnvs"] if k == "_MainTex"]
        if not tex_ids or tex_ids[0] not in grown:
            continue
        target = float(grown[tex_ids[0]])
        floats = [(k, target if k == "_TextureHeight" else v) for k, v in props["m_Floats"]]
        if floats != [tuple(p) for p in props["m_Floats"]]:
            props["m_Floats"] = floats
            obj.save_typetree(mt)
            mats += 1
    print(f"  güncellenen materyal: {mats}")

    for f in fonts.values():
        if f.name in SKIP:
            continue
        tex = f.tex_obj.read()
        rgba = np.zeros((f.H, f.W, 4), np.uint8)
        rgba[..., 3] = np.round(f.atlas).astype(np.uint8)
        tex.image = Image.fromarray(rgba, "RGBA")
        tex.save()
        f.obj.save_typetree(f.t)

    OUT_DIR.mkdir(exist_ok=True)
    FONT_OUT.write_bytes(env.file.save(packer="lz4"))
    preview(fonts, PREVIEW_OUT)
    print(f"Font paketi -> {FONT_OUT}\nÖnizleme   -> {PREVIEW_OUT}")


if __name__ == "__main__":
    main()
