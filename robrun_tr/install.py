"""Install / uninstall the Turkish patch WITHOUT touching the game folder.

How it works (Addressables 2.x content-catalog cache):
  * settings.json points the game at a "cache" catalog:
        {persistentDataPath}/com.unity.addressables/catalog_<build>.bin (+ .hash)
  * If that cached .hash equals the game's own catalog hash, the game loads the cached catalog.
  * We write a copy of the game's catalog there in which the English string-table bundle
    path is redirected to our Turkish bundle (also placed in that folder).
  * Strings in the binary catalog are length-prefixed and referenced by offset, so the
    replacement path must have exactly the same byte length -> we pad our file name.
"""
import argparse
import json
import shutil
import sys
import webbrowser
from pathlib import Path

from common import (AA_REL, CACHE_DIR, EN_BUNDLE, FONT_BUNDLE, MANIFEST, OUT_DIR, PLATFORM, STEAM_APPID,
                    find_game_dir, load_json, save_json)

RUNTIME_PREFIX = "{UnityEngine.AddressableAssets.Addressables.RuntimePath}\\" + PLATFORM + "\\"
CACHE_PREFIX = "{UnityEngine.Application.persistentDataPath}/com.unity.addressables/"


def current_catalog(game: Path):
    """Return (cache catalog base name, hash text) for the installed game build."""
    aa = game / AA_REL
    settings = json.loads((aa / "settings.json").read_text(encoding="utf-8"))
    loc = {l["m_Keys"][0]: l["m_InternalId"] for l in settings["m_CatalogLocations"]}
    cache_hash_id = loc["AddressablesMainContentCatalogCacheHash"]
    remote_hash_id = loc["AddressablesMainContentCatalogRemoteHash"]
    base = cache_hash_id.rsplit("/", 1)[1][:-len(".hash")]                       # catalog_2026.11.17...
    remote_hash_file = aa / remote_hash_id.split("RuntimePath}/", 1)[1]
    return base, remote_hash_file.read_text().strip()


def padded_name(original_id: str, stem: str) -> str:
    """Our bundle file name, padded so CACHE_PREFIX+name has the same length as original_id."""
    room = len(original_id) - len(CACHE_PREFIX) - len(".bundle")
    if room < len(stem):
        raise RuntimeError(f"Adres sığmıyor: {stem}")
    return stem + "_" * (room - len(stem)) + ".bundle"


def redirect(catalog: bytes, bundle_file: str, stem: str):
    original = (RUNTIME_PREFIX + bundle_file).encode("ascii")
    count = catalog.count(original)
    if count != 1:
        raise RuntimeError(f"Katalogda '{bundle_file}' adresi {count} kez bulundu (1 bekleniyordu). Oyun formatı değişmiş olabilir.")
    name = padded_name(original.decode(), stem)
    new = (CACHE_PREFIX + name).encode("ascii")
    assert len(new) == len(original)
    return catalog.replace(original, new), name


def uninstall(quiet=False):
    manifest = load_json(MANIFEST, {"files": []})
    removed = 0
    for f in manifest["files"]:
        p = CACHE_DIR / f
        if p.exists():
            p.unlink()
            removed += 1
    # restore any genuine cache files we moved aside during install
    for b in manifest.get("backups", []):
        src = CACHE_DIR / (b + ".robrun_tr_bak")
        if src.exists():
            src.rename(CACHE_DIR / b)
    if MANIFEST.exists():
        MANIFEST.unlink()
    if not quiet:
        print(f"Türkçe yama kaldırıldı ({removed} dosya). Oyun orijinal İngilizce haline döndü.")


def install(game: Path, with_fonts: bool):
    tr_bundle = OUT_DIR / "strings_tr.bundle"
    font_bundle = OUT_DIR / "fonts_tr.bundle"
    if not tr_bundle.exists():
        raise SystemExit("Önce build.py çalıştırılmalı (out/strings_tr.bundle yok).")

    uninstall(quiet=True)                                    # start from a clean state
    base, hash_text = current_catalog(game)
    aa = game / AA_REL
    catalog = (aa / "catalog.bin").read_bytes()
    dated = aa / PLATFORM / f"{base}.bin"
    if dated.exists() and dated.read_bytes() != catalog:   # catalog.bin damaged by another patch -> use pristine copy
        catalog = dated.read_bytes()

    catalog, tr_name = redirect(catalog, EN_BUNDLE, "robrun-tr-strings")
    files = {tr_name: tr_bundle.read_bytes()}
    if with_fonts:
        if not font_bundle.exists():
            raise SystemExit("out/fonts_tr.bundle yok; --fonts olmadan kurun.")
        catalog, font_name = redirect(catalog, FONT_BUNDLE, "robrun-tr-fonts")
        files[font_name] = font_bundle.read_bytes()
    files[f"{base}.bin"] = catalog
    files[f"{base}.hash"] = hash_text.encode("ascii")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for name in (f"{base}.bin", f"{base}.hash"):            # keep a genuine game cache, if one exists
        p = CACHE_DIR / name
        if p.exists():
            p.rename(CACHE_DIR / (name + ".robrun_tr_bak"))
            backups.append(name)
    for name, data in files.items():
        (CACHE_DIR / name).write_bytes(data)
    save_json(MANIFEST, {"files": list(files), "backups": backups, "catalog": base})

    print(f"Kuruldu -> {CACHE_DIR}")
    for name in files:
        print(f"  + {name}")
    print("Oyun klasöründe hiçbir dosya değiştirilmedi.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    ap.add_argument("--uninstall", "--kaldir", action="store_true")
    ap.add_argument("--fonts", action="store_true", help="Türkçe karakterli font paketini de kur")
    ap.add_argument("--launch", action="store_true", help="kurulumdan sonra oyunu Steam ile başlat")
    args = ap.parse_args(argv)
    if args.uninstall:
        uninstall()
        return
    install(find_game_dir(args.game), args.fonts)
    if args.launch:
        webbrowser.open(f"steam://run/{STEAM_APPID}")


if __name__ == "__main__":
    main()
