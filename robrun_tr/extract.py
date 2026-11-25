"""Extract all English strings (with their key names) into data/strings_en.json."""
import argparse

import UnityPy

from common import EN_BUNDLE, EN_JSON, SHARED_BUNDLE, bundle_dir, find_game_dir, save_json, string_tables, table_name


def read_key_names(game):
    env = UnityPy.load(str(bundle_dir(game) / SHARED_BUNDLE))
    keys = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if "m_Entries" in tree and "m_TableCollectionName" in tree:
            keys[tree["m_TableCollectionName"]] = {str(e["m_Id"]): e["m_Key"] for e in tree["m_Entries"]}
    return keys


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    args = ap.parse_args(argv)
    game = find_game_dir(args.game)

    keys = read_key_names(game)
    env = UnityPy.load(str(bundle_dir(game) / EN_BUNDLE))
    out = {}
    for _, tree in string_tables(env):
        t = table_name(tree)
        out[t] = {str(e["m_Id"]): {"key": keys.get(t, {}).get(str(e["m_Id"]), str(e["m_Id"])), "en": e["m_Localized"]}
                  for e in tree["m_TableData"]}
    save_json(EN_JSON, out)
    print(f"{sum(len(v) for v in out.values())} metin çıkarıldı -> {EN_JSON}")


if __name__ == "__main__":
    main()
