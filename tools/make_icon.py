"""Draw the app icon (assets/icon.ico): dark rounded tile, lime 'TR' in Bahnschrift."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"
OUT.parent.mkdir(exist_ok=True)

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, S - 8, S - 8), radius=52, fill=(22, 23, 26, 255), outline=(197, 251, 49, 255), width=10)
try:
    big = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 132)
    small = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 40)
except OSError:
    big = small = ImageFont.load_default()
d.text((S / 2, 118), "TR", font=big, fill=(197, 251, 49, 255), anchor="mm")
d.text((S / 2, 200), "ROB RUN", font=small, fill=(236, 236, 236, 255), anchor="mm")
img.save(OUT, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
img.save(OUT.with_suffix(".png"))
print("icon ->", OUT)
