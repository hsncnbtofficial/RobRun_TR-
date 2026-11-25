"""Build the Turkish string-table bundle from the game's English bundle + data/strings_tr.json.

The English table is rewritten in place (same locale id, same table ids), so the game
simply shows Turkish while "English" is selected. Untranslated or invalid entries keep English.
"""
import argparse
import re
from collections import Counter

import UnityPy

from common import EN_BUNDLE, FOLD_MAP, OUT_DIR, OVERLAY_JSON, TR_JSON, bundle_dir, find_game_dir, load_json, string_tables, table_name
from extract import read_key_names

TR_BUNDLE_OUT = OUT_DIR / "strings_tr.bundle"
TAG_RE = re.compile(r"<[^>]*>")
ARG_RE = re.compile(r"\{(\d+)")


def problems(en: str, tr: str):
    """Return a list of reasons the translation would break the game's formatting."""
    errs = []
    if Counter(TAG_RE.findall(en)) != Counter(TAG_RE.findall(tr)):
        errs.append("etiketler farklı")
    if Counter(ARG_RE.findall(en)) != Counter(ARG_RE.findall(tr)):
        errs.append("{n} yer tutucuları farklı")
    if en.count("{") - en.count("}") != tr.count("{") - tr.count("}"):
        errs.append("süslü parantez dengesi bozuk")
    if not tr.strip() and en.strip():
        errs.append("boş çeviri")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    ap.add_argument("--no-fold", action="store_true",
                    help="ğ/ş/ı/İ harflerini sadeleştirme (Türkçe fontlar kuruluysa)")
    ap.add_argument("--no-guide", action="store_true", help="oyun içi rehber ipuçlarını ekleme")
    args = ap.parse_args(argv)
    game = find_game_dir(args.game)
    tr = load_json(TR_JSON, {})
    overlay = {} if args.no_guide else load_json(OVERLAY_JSON, {})

    # key names live in the shared data; strings_tr uses "Table::key" (or "Table::id")
    all_keys = read_key_names(game)
    env = UnityPy.load(str(bundle_dir(game) / EN_BUNDLE))
    done = kept = bad = hints = 0
    for obj, tree in string_tables(env):
        t = table_name(tree)
        keys = all_keys.get(t, {})
        for e in tree["m_TableData"]:
            eid = str(e["m_Id"])
            full_key = f"{t}::{keys.get(eid, eid)}"
            if full_key in overlay:                      # guide hint, appended after validation
                hints += 1
            text = tr.get(full_key) or tr.get(f"{t}::{eid}")
            if text is None:
                if full_key in overlay:
                    e["m_Localized"] += overlay[full_key]
                kept += 1
                continue
            errs = problems(e["m_Localized"], text)
            if errs:
                bad += 1
                print(f"  [ATLANDI] {t}::{keys.get(eid, eid)}: {', '.join(errs)}")
                continue
            text += overlay.get(full_key, "")
            e["m_Localized"] = text if args.no_fold else text.translate(FOLD_MAP)
            done += 1
        obj.save_typetree(tree)

    OUT_DIR.mkdir(exist_ok=True)
    TR_BUNDLE_OUT.write_bytes(env.file.save(packer="lz4"))
    total = done + kept + bad
    print(f"Türkçe paket hazır -> {TR_BUNDLE_OUT}")
    print(f"  çevrildi: {done}/{total} ({done * 100 // max(total, 1)}%) | İngilizce kaldı: {kept} | hatalı: {bad}"
          f" | rehber ipucu: {hints}")


if __name__ == "__main__":
    main()
