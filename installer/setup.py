"""ROB RUN Türkçe — setup wizard (tkinter, per-user install, no admin rights needed).

Pages: Hoş geldin -> Konum/Kısayollar -> Kuruluyor -> Bitti.
Installs to %LOCALAPPDATA%\\Programs\\RobRun Turkce, creates shortcuts and an
"Uygulamalar ve özellikler" entry whose uninstall runs `RobRun_Turkce.exe --uninstall-app`.
"""
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "robrun_tr"))
from winpaths import special_folder  # noqa: E402

APP_NAME = "ROB RUN Türkçe"
APP_VERSION = "1.3.0"
PUBLISHER = "RobRun TR"
APP_EXE = "RobRun_Turkce.exe"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\RobRunTR"
DEFAULT_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\RobRun Turkce"))
PAYLOAD = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "payload"

BG, PANEL, LINE, TEXT, MUTED, ACCENT, INK = "#16171a", "#1f2024", "#34363c", "#ececec", "#8d9097", "#c5fb31", "#141500"
FONT = "Bahnschrift"


# ---------------------------------------------------------------- install logic
def game_found() -> bool:
    for hive, sub, val in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                           (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
        try:
            with winreg.OpenKey(hive, sub) as k:
                root = Path(winreg.QueryValueEx(k, val)[0])
        except OSError:
            continue
        libs = [root]
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            import re
            libs += [Path(m.replace("\\\\", "\\")) for m in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text("utf-8", "ignore"))]
        if any((lib / "steamapps" / "common" / "Rob Run" / "ROB RUN.exe").exists() for lib in libs):
            return True
    return False


def make_shortcut(lnk: Path, target: Path, workdir: Path):
    """Create a .lnk in-process through the Windows Shell COM API (no PowerShell)."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()                      # we run in a worker thread
    try:
        sc = win32com.client.Dispatch("WScript.Shell").CreateShortCut(str(lnk))
        sc.TargetPath = str(target)
        sc.WorkingDirectory = str(workdir)
        sc.IconLocation = f"{target},0"
        sc.Description = APP_NAME
        sc.save()
    finally:
        pythoncom.CoUninitialize()


def make_shortcuts_safely(jobs, exe: Path, workdir: Path, timeout=15):
    """Run shortcut creation with a hard time limit; a failure never blocks the install."""
    errors = []

    def work():
        for name, lnk_name in jobs:
            try:
                make_shortcut(special_folder(name) / lnk_name, exe, workdir)
            except Exception as e:
                errors.append(f"{name}: {e}")
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        errors.append("zaman aşımı")
    return errors


def do_install(target: Path, desktop: bool, startmenu: bool, step):
    step(5, "Çalışan program kapatılıyor...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", APP_EXE], capture_output=True, timeout=10,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

    step(15, "Dosyalar kopyalanıyor...")
    target.mkdir(parents=True, exist_ok=True)
    import time
    for f in PAYLOAD.iterdir():
        for attempt in range(30):                 # a just-closed exe can stay locked for a few seconds
            try:
                shutil.copy2(f, target / f.name)
                break
            except PermissionError:
                if attempt == 29:
                    raise
                time.sleep(0.5)
    exe = target / APP_EXE

    step(60, "Kısayollar oluşturuluyor...")
    jobs = ([("Desktop", f"{APP_NAME}.lnk")] if desktop else []) + ([("Programs", f"{APP_NAME}.lnk")] if startmenu else [])
    shortcut_errors = make_shortcuts_safely(jobs, exe, target) if jobs else []

    step(85, "Windows'a kaydediliyor...")
    size_kb = sum(f.stat().st_size for f in target.iterdir() if f.is_file()) // 1024
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
        for name, val in [("DisplayName", APP_NAME), ("DisplayVersion", APP_VERSION), ("Publisher", PUBLISHER),
                          ("InstallLocation", str(target)), ("DisplayIcon", f"{exe},0"),
                          ("UninstallString", f'"{exe}" --uninstall-app')]:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        for name, val in [("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", size_kb)]:
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)
    step(100, "Kurulum tamamlandı.")
    return exe, shortcut_errors


# ---------------------------------------------------------------- wizard UI
class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION} Kurulumu")
        self.geometry("680x460")
        self.resizable(False, False)
        self.configure(bg=BG)
        icon = PAYLOAD / "icon.ico"
        if icon.exists():
            self.iconbitmap(str(icon))
        self.target = tk.StringVar(value=str(DEFAULT_DIR))
        self.desktop = tk.BooleanVar(value=True)
        self.startmenu = tk.BooleanVar(value=True)
        self.launch = tk.BooleanVar(value=True)
        self.exe = None

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("A.Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT, bordercolor=LINE,
                        lightcolor=ACCENT, darkcolor=ACCENT, thickness=14)

        side = tk.Frame(self, bg="#111214", width=200)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="ROB RUN", bg="#111214", fg=TEXT, font=(FONT, 22, "bold italic")).pack(anchor="w", padx=20, pady=(28, 0))
        tk.Label(side, text="TÜRKÇE", bg="#111214", fg=ACCENT, font=(FONT, 22, "bold italic")).pack(anchor="w", padx=20)
        self.steps = []
        for s in ["Hoş geldin", "Kurulum ayarları", "Kuruluyor", "Bitti"]:
            lbl = tk.Label(side, text=s, bg="#111214", fg=MUTED, font=(FONT, 11), anchor="w")
            lbl.pack(fill="x", padx=20, pady=(14 if not self.steps else 4, 0))
            self.steps.append(lbl)
        tk.Label(side, text=f"Sürüm {APP_VERSION}", bg="#111214", fg=MUTED, font=(FONT, 9)).pack(side="bottom", anchor="w", padx=20, pady=16)

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(side="top", fill="both", expand=True, padx=28, pady=(26, 0))
        bar = tk.Frame(self, bg=BG)
        bar.pack(side="bottom", fill="x", padx=28, pady=20)
        self.btn_next = self._button(bar, "İleri", self.next, primary=True)
        self.btn_next.pack(side="right")
        self.btn_back = self._button(bar, "Geri", self.back)
        self.btn_back.pack(side="right", padx=8)
        self.btn_cancel = self._button(bar, "İptal", self.cancel)
        self.btn_cancel.pack(side="left")
        self.page = 0
        self.show()

    # widgets
    def _button(self, parent, text, cmd, primary=False):
        return tk.Button(parent, text=text.upper(), command=cmd, bd=0, padx=20, pady=8, cursor="hand2",
                         font=(FONT, 11, "bold" if primary else "normal"),
                         bg=ACCENT if primary else PANEL, fg=INK if primary else TEXT,
                         activebackground=ACCENT if primary else LINE, activeforeground=INK if primary else TEXT)

    def _h(self, text):
        tk.Label(self.body, text=text.upper(), bg=BG, fg=TEXT, font=(FONT, 20, "bold italic"), anchor="w").pack(fill="x")

    def _p(self, text, color=MUTED, pady=(8, 0)):
        tk.Label(self.body, text=text, bg=BG, fg=color, font=(FONT, 11), justify="left", anchor="w",
                 wraplength=420).pack(fill="x", pady=pady)

    def _check(self, text, var):
        tk.Checkbutton(self.body, text=text, variable=var, bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG,
                       activeforeground=TEXT, font=(FONT, 11), anchor="w", highlightthickness=0).pack(fill="x", pady=2)

    # navigation
    def show(self):
        for w in self.body.winfo_children():
            w.destroy()
        for i, l in enumerate(self.steps):
            l.configure(fg=ACCENT if i == self.page else (TEXT if i < self.page else MUTED),
                        font=(FONT, 11, "bold" if i == self.page else "normal"))
        getattr(self, f"page{self.page}")()

    def next(self):
        if self.page == 1:
            self.page = 2
            self.show()
            return
        if self.page == 3:
            return self.finish()
        self.page += 1
        self.show()

    def back(self):
        if self.page in (1,):
            self.page -= 1
            self.show()

    def cancel(self):
        if self.page == 2:
            return
        if self.page == 3 or messagebox.askyesno("Kurulum", "Kurulumdan çıkılsın mı?", parent=self):
            self.destroy()

    # pages
    def page0(self):
        self._h("Hoş geldin")
        self._p("Bu sihirbaz ROB RUN Türkçe programını bilgisayarına kuracak.", TEXT, (14, 0))
        self._p("Program; oyunun tamamını Türkçeye çevirir, fontlara Türkçe harfleri ekler ve "
                "soygun hedefleri, anahtarlar ve yükseltmeler için bir suç rehberi sunar.")
        self._p("Oyun klasöründeki hiçbir dosya değiştirilmez.")
        if game_found():
            self._p("✔ Rob Run bu bilgisayarda bulundu.", "#5fd38d", (18, 0))
        else:
            self._p("⚠ Rob Run bulunamadı. Programı yine de kurabilirsin; Türkçe yamayı oyun kurulduktan sonra uygularsın.",
                    "#ffb340", (18, 0))
        self.btn_back.configure(state="disabled")
        self.btn_next.configure(text="İLERİ", state="normal")

    def page1(self):
        self._h("Kurulum ayarları")
        self._p("Kurulum klasörü:", TEXT, (14, 4))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        tk.Entry(row, textvariable=self.target, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=(FONT, 10)).pack(side="left", fill="x", expand=True, ipady=7)
        self._button(row, "Gözat", self.browse).pack(side="left", padx=(8, 0))
        self._p("Yönetici izni gerekmez; program sadece senin kullanıcı hesabına kurulur.")
        tk.Frame(self.body, bg=BG, height=12).pack()
        self._check("Masaüstüne kısayol oluştur", self.desktop)
        self._check("Başlat menüsüne kısayol oluştur", self.startmenu)
        self.btn_back.configure(state="normal")
        self.btn_next.configure(text="KUR")

    def browse(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.target.get())
        if d:
            self.target.set(str(Path(d) / "RobRun Turkce"))

    def page2(self):
        self._h("Kuruluyor")
        self.status = tk.Label(self.body, text="Hazırlanıyor...", bg=BG, fg=MUTED, font=(FONT, 11), anchor="w")
        self.status.pack(fill="x", pady=(18, 8))
        self.bar = ttk.Progressbar(self.body, style="A.Horizontal.TProgressbar", maximum=100)
        self.bar.pack(fill="x")
        for b in (self.btn_next, self.btn_back, self.btn_cancel):
            b.configure(state="disabled")
        threading.Thread(target=self._install_thread, daemon=True).start()

    def _install_thread(self):
        def step(pct, msg):
            self.after(0, lambda: (self.bar.configure(value=pct), self.status.configure(text=msg)))
        try:
            self.exe, self.shortcut_errors = do_install(Path(self.target.get()), self.desktop.get(),
                                                        self.startmenu.get(), step)
            self.after(400, self._done)
        except Exception as e:
            self.after(0, lambda: self._failed(e))

    def _failed(self, e):
        messagebox.showerror("Kurulum başarısız",
                             f"Kurulum tamamlanamadı:\n{e}\n\nProgram açıksa kapatıp tekrar dene.", parent=self)
        self.page = 1
        self.btn_cancel.configure(state="normal")
        self.btn_next.configure(state="normal")
        self.show()

    def _done(self):
        self.page = 3
        self.show()

    def page3(self):
        self._h("Kurulum tamamlandı")
        self._p(f"{APP_NAME} kuruldu.", TEXT, (14, 0))
        if getattr(self, "shortcut_errors", None):
            self._p("⚠ Kısayol oluşturulamadı (antivirüs engellemiş olabilir). Programı şuradan açabilirsin: "
                    f"{self.exe}", "#ffb340")
        self._p("Programı açıp \"Kur ve Oyunu Başlat\" butonuna basman yeterli: "
                "oyun Türkçe olarak açılır. Oyun güncellenince aynı butona tekrar basman yeterli.")
        self._p("Kaldırmak için: Ayarlar > Uygulamalar > Yüklü uygulamalar > ROB RUN Türkçe.")
        tk.Frame(self.body, bg=BG, height=12).pack()
        self._check("ROB RUN Türkçe'yi şimdi başlat", self.launch)
        self.btn_back.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.btn_next.configure(text="BİTİR", state="normal")

    def finish(self):
        if self.launch.get() and self.exe:
            subprocess.Popen([str(self.exe)], cwd=str(self.exe.parent))
        self.destroy()


if __name__ == "__main__":
    if "--silent" in sys.argv:                    # used for automated testing; never shows a crash dialog
        try:
            do_install(DEFAULT_DIR, "--no-shortcuts" not in sys.argv, "--no-shortcuts" not in sys.argv, lambda p, m: None)
        except Exception as e:
            sys.exit(f"kurulum hatası: {e}")
    else:
        Wizard().mainloop()
