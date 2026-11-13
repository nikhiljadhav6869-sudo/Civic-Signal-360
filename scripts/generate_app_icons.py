"""Reproduce the code-drawn water/signal app icon; no external image assets."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'apps/web/public/icons'
target.mkdir(parents=True, exist_ok=True)
canvas = Image.new('RGB', (1024, 1024), '#09121c')
draw = ImageDraw.Draw(canvas)
# Central artwork stays inside the maskable icon's 80% safe circle.
draw.ellipse((254, 416, 662, 824), fill='#20d8db')
draw.polygon([(254, 608), (458, 226), (662, 608)], fill='#20d8db')
draw.arc((350, 456, 596, 738), 20, 95, fill='#09121c', width=36)
draw.arc((564, 196, 770, 402), 270, 360, fill='#20d8db', width=36)
draw.arc((494, 126, 840, 472), 270, 360, fill='#20d8db', width=36)
for filename, size in [('icon-192.png', 192), ('icon-512.png', 512), ('maskable-512.png', 512), ('apple-touch-icon.png', 180)]:
    canvas.resize((size, size), Image.Resampling.LANCZOS).save(target / filename)
print('Generated four local application icons.')
