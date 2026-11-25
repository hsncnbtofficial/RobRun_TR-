"""ROB RUN Türkçe — desktop launcher (pywebview).

Tabs: Türkçe Yama (install/uninstall/launch) + Rehber (progress, heist targets, keys, upgrades).
All patching happens in %LOCALAPPDATA%Low cache; the game folder is never modified.
"""
import contextlib
import hashlib
import io
import json
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT / "robrun_tr"))

import webview  # noqa: E402

import build  # noqa: E402
import fonts  # noqa: E402
import install  # noqa: E402
import live  # noqa: E402
from common import (CACHE_DIR, DATA_DIR, FONT_BUNDLE, MANIFEST, OUT_DIR, STEAM_APPID, USER_DIR,  # noqa: E402
                    bundle_dir, find_game_dir, load_json, save_json)

APP_VERSION = "1.3.0"
UI = ROOT / "app" / "ui" / "index.html"
STATE = USER_DIR / "state.json"
FONT_SRC_MD5 = OUT_DIR / "fonts_tr.src.md5"
# in-game item titles whose tooltip price can be learned from the screen -> recommendation id in the UI
PRICE_NAMES = {"Mini Matkap": "minidrill", "Maymuncuk": "lockpick", "Para Sayma Makinesi": "counter",
               "Kargo Tezgâhı": "cargo", "Koleksiyon Masası": "collection", "Kaçak Mal Tezgâhı": "contraband",
               "Bagaj Çantaları": "trunk", "Elektronik Sigorta": "defense", "Yerleşim Tapusu": "settlement"}


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class LogTee(io.TextIOBase):
    def __init__(self, sink):
        self.sink = sink

    def write(self, s):
        if s.strip():
            self.sink(s.rstrip())
        return len(s)


class Api:
    def __init__(self):
        self.log = []
        self.busy = False
        self.reader = None

    # ---------- live game reading (screen OCR, no memory access) ----------
    def start_live(self):
        if self.reader is None:
            self.reader = live.LiveReader(item_names=list(PRICE_NAMES))
            threading.Thread(target=self.reader.run, daemon=True).start()

    def live(self):
        if self.reader is None:
            return {"running": False}
        st = dict(self.reader.state)
        st["prices"] = {PRICE_NAMES[n]: v for n, v in st.get("prices", {}).items() if n in PRICE_NAMES}
        return st

    # ---------- helpers ----------
    def _log(self, line):
        self.log.append(line)

    def _run(self, fn):
        if self.busy:
            return False
        self.busy = True
        self.log = []

        def worker():
            try:
                with contextlib.redirect_stdout(LogTee(self._log)):
                    fn()
                self._log("✔ Tamamlandı.")
            except SystemExit as e:
                self._log(f"✖ {e}")
            except Exception as e:  # show the reason in the UI, keep the app alive
                self._log(f"✖ Hata: {e}")
                self._log(traceback.format_exc(limit=2))
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()
        return True

    # ---------- patch ----------
    def status(self):
        try:
            game = find_game_dir()
        except SystemExit:
            return {"game": None, "installed": False, "version": APP_VERSION}
        manifest = load_json(MANIFEST, None)
        current = install.current_catalog(game)[0]
        installed = bool(manifest) and manifest.get("catalog") == current
        return {"game": str(game), "installed": installed, "outdated": bool(manifest) and not installed,
                "catalog": current, "version": APP_VERSION}

    def install(self, guide_hints=True, launch=False):
        def job():
            game = find_game_dir()
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            src = md5(bundle_dir(game) / FONT_BUNDLE)
            cached = FONT_SRC_MD5.read_text() if FONT_SRC_MD5.exists() else ""
            if cached != src or not (OUT_DIR / "fonts_tr.bundle").exists():
                print("Türkçe fontlar hazırlanıyor (ilk kurulumda ~1 dk)...")
                fonts.main(["--game", str(game)])
                FONT_SRC_MD5.write_text(src)
            else:
                print("Fontlar güncel, önbellekten kullanılıyor.")
            print("Türkçe metin paketi oluşturuluyor...")
            build.main(["--game", str(game), "--no-fold"] + ([] if guide_hints else ["--no-guide"]))
            install.main(["--game", str(game), "--fonts"])
            if launch:
                webbrowser.open(f"steam://run/{STEAM_APPID}")
                print("Oyun Steam üzerinden başlatılıyor...")
        return self._run(job)

    def uninstall(self):
        return self._run(lambda: install.main(["--uninstall"]))

    def launch(self):
        webbrowser.open(f"steam://run/{STEAM_APPID}")
        return True

    def poll(self):
        return {"busy": self.busy, "log": self.log}

    # ---------- guide ----------
    def guide(self):
        return load_json(DATA_DIR / "guide.json", {})

    def load_state(self):
        return load_json(STATE, {})

    def save_state(self, state):
        save_json(STATE, state)
        return True


def selftest():
    """Headless check of the packaged app: status + full install, log to %LOCALAPPDATA%\\RobRunTR."""
    import time
    api = Api()
    out = [f"status: {api.status()}", f"guide targets: {len(api.guide().get('targets', []))}"]
    api.install(True, False)
    time.sleep(1)
    while api.busy:
        time.sleep(0.5)
    out += api.log + [f"status: {api.status()}"]
    USER_DIR.mkdir(parents=True, exist_ok=True)
    (USER_DIR / "selftest.log").write_text("\n".join(out), encoding="utf-8")


def uninstall_app():
    """Called from Windows 'Uygulamalar ve özellikler': remove patch, shortcuts, registry entry and program folder."""
    import ctypes
    import shutil
    import subprocess
    import winreg

    reg_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\RobRunTR"
    title = "ROB RUN Türkçe"
    if "--quiet" not in sys.argv:
        yes = ctypes.windll.user32.MessageBoxW(None, "ROB RUN Türkçe ve Türkçe yama kaldırılsın mı?\n"
                                                     "Oyun orijinal İngilizce hâline döner.", title, 0x24) == 6
        if not yes:
            return
    with contextlib.suppress(Exception):
        with contextlib.redirect_stdout(io.StringIO()):
            install.main(["--uninstall"])                    # game back to English
    location = None
    with contextlib.suppress(OSError):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key) as k:
            location = Path(winreg.QueryValueEx(k, "InstallLocation")[0])
    with contextlib.suppress(OSError):
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_key)
    from winpaths import special_folder
    for folder in ("Desktop", "Programs"):
        with contextlib.suppress(OSError):
            (special_folder(folder) / f"{title}.lnk").unlink()
    shutil.rmtree(USER_DIR, ignore_errors=True)               # cached bundles + guide progress
    me = Path(sys.executable).resolve()
    if location and getattr(sys, "frozen", False) and me.parent == location.resolve() and (location / me.name).exists():
        # this exe is running: let a detached shell delete the folder after we exit
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q "{location}"',
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS, close_fds=True)
    if "--quiet" not in sys.argv:
        ctypes.windll.user32.MessageBoxW(None, "ROB RUN Türkçe kaldırıldı.", title, 0x40)


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--uninstall-app" in sys.argv:
        return uninstall_app()
    if "--ocrtest" in sys.argv:                      # packaged OCR check on given screenshot files
        from PIL import Image
        files = sys.argv[sys.argv.index("--ocrtest") + 1:]
        res = []
        for f in files:
            try:
                res.append(f"{f}: {({k: v for k, v in live.analyze(Image.open(f)).items() if k != 'texts'})}")
            except Exception:
                res.append(f"{f}: HATA\n{traceback.format_exc()}")
        USER_DIR.mkdir(parents=True, exist_ok=True)
        (USER_DIR / "ocrtest.log").write_text("\n".join(res), encoding="utf-8")
        return
    api = Api()
    api.start_live()
    webview.create_window(f"ROB RUN Türkçe {APP_VERSION}", str(UI), js_api=api,
                          width=1240, height=820, min_size=(980, 640), background_color="#16171a")
    webview.start()


if __name__ == "__main__":
    main()
