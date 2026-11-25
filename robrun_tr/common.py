"""Shared paths and helpers for the Rob Run Turkish translation tool."""
import json
import os
import re
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)                  # running from the packaged .exe
PROJECT = Path(__file__).resolve().parent.parent
RES_DIR = Path(getattr(sys, "_MEIPASS", PROJECT))        # read-only bundled resources
USER_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\RobRunTR"))
DATA_DIR = RES_DIR / "data"
OUT_DIR = (USER_DIR / "out") if FROZEN else (PROJECT / "out")
EN_JSON = DATA_DIR / "strings_en.json"   # {table: {id: {"key": k, "en": text}}}
TR_JSON = DATA_DIR / "strings_tr.json"   # {"Table::key": "turkish text"}
OVERLAY_JSON = DATA_DIR / "strings_overlay.json"   # guide hints appended in-game {"Table::key": suffix}

STEAM_APPID = "4262460"
GAME_EXE = "ROB RUN.exe"
AA_REL = Path("ROB RUN_Data/StreamingAssets/aa")
PLATFORM = "StandaloneWindows64"
EN_BUNDLE = "localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle"
SHARED_BUNDLE = "localization-assets-shared_assets_all.bundle"
FONT_BUNDLE = "inbuild_assets_all.bundle"

# Unity persistentDataPath for this game (company "Kefir", product "ROB RUN")
CACHE_DIR = Path(os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Kefir\ROB RUN\com.unity.addressables"))
MANIFEST = CACHE_DIR / "robrun_tr_manifest.json"

# Glyphs the game's fonts do not contain (until we ship patched fonts).
FOLD_MAP = str.maketrans({"ğ": "g", "Ğ": "G", "ş": "s", "Ş": "S", "ı": "i", "İ": "I"})


def find_game_dir(explicit=None) -> Path:
    """Locate the Rob Run install via an explicit path or Steam library folders."""
    if explicit:
        p = Path(explicit)
        if (p / GAME_EXE).exists():
            return p
        raise SystemExit(f"Oyun bulunamadı: {p}")
    steam_roots = []
    try:
        import winreg
        for hive, sub, val in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
            try:
                with winreg.OpenKey(hive, sub) as k:
                    steam_roots.append(Path(winreg.QueryValueEx(k, val)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    steam_roots.append(Path(r"C:\Program Files (x86)\Steam"))
    libs = []
    for root in steam_roots:
        libs.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text("utf-8", "ignore")):
                libs.append(Path(m.group(1).replace("\\\\", "\\")))
    for lib in libs:
        cand = lib / "steamapps" / "common" / "Rob Run"
        if (cand / GAME_EXE).exists():
            return cand
    raise SystemExit("Rob Run kurulumu bulunamadı. --game ile klasörü belirtin.")


def bundle_dir(game: Path) -> Path:
    return game / AA_REL / PLATFORM


def string_tables(env):
    """Yield (object, typetree) for every Unity Localization StringTable in a bundle."""
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if "m_TableData" in tree and "m_LocaleId" in tree:
            yield obj, tree


def table_name(tree) -> str:
    return tree["m_Name"].rsplit("_", 1)[0]          # "StaticStrings_en-US" -> "StaticStrings"


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
