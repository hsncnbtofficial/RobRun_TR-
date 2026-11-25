"""Build the heist/progression guide from game data + data/guide_curated.json.

Outputs:
  data/guide.json            full guide for the desktop app
  data/strings_overlay.json  short in-game hints appended to existing texts ("Table::key" -> suffix)

In-game hints only use plain text and <color> tags (no braces: texts go through SmartFormat).
"""
import argparse
import json
import re

import UnityPy

from common import DATA_DIR, EN_JSON, TR_JSON, bundle_dir, find_game_dir, load_json, save_json

SO_BUNDLE = "scriptableobjects_assets_all.bundle"
CURATED = DATA_DIR / "guide_curated.json"
GUIDE_OUT = DATA_DIR / "guide.json"
OVERLAY_OUT = DATA_DIR / "strings_overlay.json"
ACCENT = "#C5FB31"


def read_game_data(game):
    """Locations (title/description key ids + loot) and inventory items (name/description key ids)."""
    env = UnityPy.load(str(bundle_dir(game) / SO_BUNDLE))
    locs, items = {}, {}
    kid = lambda ref: str(ref["m_TableEntryReference"]["m_KeyId"])
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        t = o.read_typetree()
        if "<Rewards>k__BackingField" in t:
            locs[t["m_Name"]] = {"title": kid(t["<Title>k__BackingField"]), "desc": kid(t["<Description>k__BackingField"]),
                                 "rewards": [r["_id"] for r in t["<Rewards>k__BackingField"]]}
        elif t.get("m_Name") == "InventoryItemViewDescriptions":
            arr = next(v for v in t.values() if isinstance(v, list) and v and isinstance(v[0], dict)
                       and "<Identified>k__BackingField" in v[0])
            for it in arr:
                items[it["<Identified>k__BackingField"]["_id"]] = {"name": kid(it["<Name>k__BackingField"]),
                                                                   "desc": kid(it["<Description>k__BackingField"])}
    return locs, items


def stars(n):
    return f"{n}/5"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    args = ap.parse_args(argv)
    game = find_game_dir(args.game)
    cur = load_json(CURATED)
    en = load_json(EN_JSON)["StaticStrings"]                 # id -> {key, en}
    tr = load_json(TR_JSON, {})
    locs, items = read_game_data(game)

    def key_of(kid):
        e = en.get(kid)
        return e["key"] if e else None

    def text(kid):
        e = en.get(kid)
        if not e:
            return None
        return re.sub(r"<[^>]*>", "", tr.get("StaticStrings::" + e["key"]) or e["en"])

    by_key = {e["key"]: e for e in en.values()}

    def item_name(iid):
        it = items.get(iid)
        if it and text(it["name"]):
            return text(it["name"])
        e = by_key.get(iid + "_name")                         # not an inventory item, but has a name string
        return (tr.get("StaticStrings::" + iid + "_name") or e["en"]) if e else iid

    problems = [i for i in list(cur["item_value"]) + list(cur["tools"]) if i not in items and i + "_name" not in by_key]
    problems += [k for t in cur["targets"] for k in t["keys"] + t["needs"] if k not in items]
    problems += [t["loc"] for t in cur["targets"] if t["loc"] not in locs]
    if problems:
        print("UYARI: oyunda bulunamayan kimlikler:", sorted(set(problems)))

    # ---- full guide for the app ----
    targets = []
    for t in cur["targets"]:
        loc = locs.get(t["loc"], {"rewards": [], "title": None})
        loot = [{"id": r, "name": item_name(r), "value": cur["item_value"].get(r)} for r in loc["rewards"]]
        vals = [l["value"] for l in loot if l["value"]]
        targets.append({
            "id": t["loc"], "name": text(loc["title"]) or t["loc"], "area": cur["areas"][t["area"]],
            "risk": t["risk"], "value": max(vals) if vals else 1, "loot": loot, "tip": t["tip"],
            "keys": [{"id": k, "name": item_name(k), "desc": text(items[k]["desc"]) if k in items else ""} for k in t["keys"]],
            "needs": [{"id": n, "name": item_name(n), "how": cur["tools"].get(n, "")} for n in t["needs"]],
        })
    tools = [{"id": i, "name": item_name(i), "how": how} for i, how in cur["tools"].items()]
    guide = {"areas": cur["areas"], "targets": targets, "tools": tools, "stages": cur["stages"], "upgrades": cur["upgrades"]}
    save_json(GUIDE_OUT, guide)

    # ---- short in-game hints ----
    overlay = {}
    tag = f"<color={ACCENT}>REHBER</color>"
    for t in targets:
        loc = locs.get(t["id"])
        k = key_of(loc["desc"]) if loc else None
        if not k:
            continue
        parts = [f"Değer {stars(t['value'])}", f"Risk {stars(t['risk'])}"]
        if t["needs"]:
            parts.append("Gerekli: " + ", ".join(n["name"] for n in t["needs"]))
        if t["keys"]:
            kinds = sorted({k_["name"] for k_ in t["keys"]})
            parts.append("Anahtar: " + ", ".join(kinds))
        overlay["StaticStrings::" + k] = f"\n{tag} " + " · ".join(parts)
    # keys: what is behind the door
    for t in targets:
        for k_ in t["keys"]:
            it = items.get(k_["id"])
            dk = key_of(it["desc"]) if it else None
            if dk and t["loot"]:
                best = sorted(t["loot"], key=lambda l: -(l["value"] or 0))[:2]
                overlay.setdefault("StaticStrings::" + dk,
                                   f"\n{tag} Mekân değeri {stars(t['value'])}, risk {stars(t['risk'])}. Öne çıkan ganimet: "
                                   + ", ".join(b["name"] for b in best))
    # tools: how to get them
    for i, how in cur["tools"].items():
        it = items.get(i)
        dk = key_of(it["desc"]) if it else None
        if dk:
            overlay["StaticStrings::" + dk] = f"\n{tag} {how}"
    # loot items: value + where to find
    where = {}
    for t in targets:
        for l in t["loot"]:
            where.setdefault(l["id"], []).append(t["name"])
    for iid, val in cur["item_value"].items():
        it = items.get(iid)
        dk = key_of(it["desc"]) if it else None
        if dk and "StaticStrings::" + dk not in overlay:
            places = sorted(set(where.get(iid, [])))[:2]
            overlay["StaticStrings::" + dk] = f"\n{tag} Değer {stars(val)}" + (f" · Bulunur: {', '.join(places)}" if places else "")
    # some game fonts lack typographic symbols: keep in-game hints to plain ASCII punctuation
    overlay = {k: v.replace(" · ", " | ").replace("→", ">") for k, v in overlay.items()}
    bad = [k for k, v in overlay.items() if "{" in v or "}" in v]
    assert not bad, bad
    save_json(OVERLAY_OUT, overlay)
    print(f"Rehber: {len(targets)} hedef, {len(tools)} alet, {len(guide['stages'])} aşama -> {GUIDE_OUT}")
    print(f"Oyun içi ipucu: {len(overlay)} metin -> {OVERLAY_OUT}")


if __name__ == "__main__":
    main()
