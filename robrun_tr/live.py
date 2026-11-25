"""Live game reader: detects ROB RUN and reads on-screen money with Windows' built-in OCR.

Safe by design: it only looks at pixels of the game window (like OBS/Discord screen share).
It never opens the game process, reads its memory or touches its network traffic.

Recognised places (relative to the game window):
  * top-right money box on Black Market / Shipments screens  -> "cash"
  * money next to the ÇANTA (bag) header in the inventory      -> "bag"
  * tooltips with an item name + "$" price                     -> learned prices
"""
import asyncio
import ctypes
import ctypes.wintypes as wt
import re
import time

from PIL import Image

GAME_EXE = "ROB RUN.exe"
MONEY_RE = re.compile(r"\$\s?(\d{1,3}(?:[.,]\s?\d{3})+|\d+)(?:\s?([KkMm]))?")

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()          # real pixel coordinates for window rects
except Exception:
    pass


# ------------------------------------------------------------------ OCR
_engine = None


def _ocr_engine():
    global _engine
    if _engine is None:
        from winrt.windows.media.ocr import OcrEngine
        _engine = OcrEngine.try_create_from_user_profile_languages()
    return _engine


async def _recognize(img: Image.Image):
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter
    rgba = img.convert("RGBA")
    b, g, r, a = rgba.split()[2], rgba.split()[1], rgba.split()[0], rgba.split()[3]
    bgra = Image.merge("RGBA", (b, g, r, a)).tobytes()
    w = DataWriter()
    w.write_bytes(bgra)
    bmp = SoftwareBitmap.create_copy_from_buffer(w.detach_buffer(), BitmapPixelFormat.BGRA8, img.width, img.height,
                                                 BitmapAlphaMode.PREMULTIPLIED)
    return await _ocr_engine().recognize_async(bmp)


def ocr_lines(img: Image.Image, scale: float = 1.0):
    """[(text, x, y, w, h)] per OCR line, in coordinates of `img` (before scaling)."""
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    res = asyncio.run(_recognize(img))
    out = []
    for line in res.lines:
        words = list(line.words)
        if not words:
            continue
        xs = [w.bounding_rect.x for w in words]
        ys = [w.bounding_rect.y for w in words]
        x2 = [w.bounding_rect.x + w.bounding_rect.width for w in words]
        y2 = [w.bounding_rect.y + w.bounding_rect.height for w in words]
        out.append((line.text, min(xs) / scale, min(ys) / scale, (max(x2) - min(xs)) / scale, (max(y2) - min(ys)) / scale))
    return out


GROUPED = re.compile(r"^\d{1,3}(?:[.,]\d{3})*$")
DOLLAR_LIKE = "$sSşŞ5§9"
DIGIT_FIX = str.maketrans({"ı": "1", "i": "1", "l": "1", "I": "1", "|": "1", "!": "1", "O": "0", "o": "0", "B": "8"})


def money_in_box(text: str):
    """Read a '$12.345' value from a UI money box where OCR may garble the '$' glyph.

    The game always prints '$' first, so a leading '$'-look-alike (s, ş, 5, 9...) is dropped,
    look-alike letters are mapped to digits and the result must be a grouped number.
    """
    tok = text.strip().split(" ")[0] if text.strip() else ""
    if not tok:
        return None
    if tok[0] == "$":
        tok = tok[1:]
    elif tok[0] in DOLLAR_LIKE and len(tok) > 1:
        rest = tok[1:].translate(DIGIT_FIX)
        if GROUPED.match(rest):
            tok = rest
    tok = tok.translate(DIGIT_FIX)
    return int(re.sub(r"[.,]", "", tok)) if GROUPED.match(tok) else None


def parse_money(text: str):
    m = MONEY_RE.search(text.replace("S", "$") if "$" not in text and re.search(r"S\d", text) else text)
    if not m:
        return None
    n = int(re.sub(r"[^\d]", "", m.group(1)))
    if m.group(2):
        n *= 1000 if m.group(2).lower() == "k" else 1_000_000
    return n


# ------------------------------------------------------------------ screen analysis
def analyze(img: Image.Image, item_names=None):
    """Find money values on a game screenshot. Returns dict(cash, bag, prices{name: n}, texts)."""
    W, H = img.size
    lines = ocr_lines(img, 1.0)
    found = {"cash": None, "bag": None, "prices": {}, "texts": [l[0] for l in lines]}
    for text, x, y, w, h in lines:
        cx, cy = (x + w / 2) / W, (y + h / 2) / H
        if cx > 0.88 and 0.03 < cy < 0.10:               # top-right money box (Karaborsa / Sevkiyatlar)
            v = money_in_box(text)
            if v is not None:
                found["cash"] = v
        elif 0.70 < cx < 0.86 and 0.10 < cy < 0.22:      # next to the ÇANTA header in the inventory
            v = money_in_box(text)
            if v is not None:
                found["bag"] = v
    if item_names:                                        # tooltip: known item title + a price below it
        up = lambda s: s.replace("i", "İ").replace("ı", "I").upper()
        for i, (text, x, y, w, h) in enumerate(lines):
            name = next((n for n in item_names if up(n) in up(text)), None)
            if not name:
                continue
            for t2, x2, y2, w2, h2 in lines[i + 1:i + 14]:
                if 0 < y2 - y < H * 0.35 and abs(x2 - x) < W * 0.25:
                    v = parse_money(t2)
                    if v:
                        found["prices"][name] = v
                        break
    return found


# ------------------------------------------------------------------ game window
def game_running() -> bool:
    import psutil
    return any((p.info["name"] or "").lower() == GAME_EXE.lower() for p in psutil.process_iter(["name"]))


def find_game_window():
    """(hwnd, rect) of the visible ROB RUN window, or (None, None)."""
    result = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.strip().upper() == "ROB RUN":
                result.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    if not result:
        return None, None
    hwnd = result[0]
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return hwnd, (pt.x, pt.y, pt.x + r.right, pt.y + r.bottom)


def capture(rect):
    import mss
    x1, y1, x2, y2 = rect
    with mss.mss() as s:
        shot = s.grab({"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1})
    return Image.frombytes("RGB", shot.size, shot.rgb)


class LiveReader:
    """Polls the game every few seconds; keeps the last values seen on screen."""

    def __init__(self, item_names=None, interval=2.5):
        self.item_names = item_names or []
        self.interval = interval
        self.state = {"running": False, "visible": False, "focused": False, "cash": None, "bag": None,
                      "cash_at": None, "bag_at": None, "prices": {}, "error": None}
        self._stop = False

    def tick(self):
        st = self.state
        st["running"] = game_running()
        hwnd, rect = find_game_window() if st["running"] else (None, None)
        st["visible"] = bool(hwnd)
        st["focused"] = bool(hwnd) and user32.GetForegroundWindow() == hwnd
        if not (st["visible"] and st["focused"]) or rect[2] - rect[0] < 400:
            return
        img = capture(rect)
        if img.getextrema() == ((0, 0), (0, 0), (0, 0)):
            st["error"] = "black"                      # exclusive fullscreen can't be captured
            return
        st["error"] = None
        f = analyze(img, self.item_names)
        now = time.time()
        if f["cash"] is not None:
            st["cash"], st["cash_at"] = f["cash"], now
        if f["bag"] is not None:
            st["bag"], st["bag_at"] = f["bag"], now
        st["prices"].update(f["prices"])

    def run(self):
        while not self._stop:
            try:
                self.tick()
            except Exception as e:                       # never crash the app because of a capture hiccup
                self.state["error"] = str(e)
            time.sleep(self.interval)

    def stop(self):
        self._stop = True
