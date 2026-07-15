"""Generate the Yazaki Bellmounth app icon: white telescope on Yazaki red.

Outputs app_icon.png (preview) and app_icon.ico (multi-size, for the exe,
shortcuts, and installer). Run: py -3.11 make_icon.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
RED = (175, 21, 29, 255)        # Yazaki red (#AF151D)
WHITE = (255, 255, 255, 255)
S = 4                            # supersampling factor
SIZE = 512


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def main():
    c = SIZE * S
    img = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    rounded_rect(d, (0, 0, c - 1, c - 1), radius=int(c * 0.22), fill=RED)

    # Telescope axis: pointing up-right at 35 degrees.
    ang = math.radians(35)
    ax = (math.cos(ang), -math.sin(ang))          # along the tube
    px = (math.sin(ang), math.cos(ang))           # perpendicular
    cx, cy = 0.42 * c, 0.52 * c                   # pivot on the tube

    def pt(t, w):
        return (cx + t * ax[0] + w * px[0], cy + t * ax[1] + w * px[1])

    def segment(t0, t1, w):
        d.polygon([pt(t0, -w), pt(t1, -w), pt(t1, w), pt(t0, w)], fill=WHITE)

    u = c / 512.0
    # Eyepiece cap, eyepiece tube, main tube, objective tube, objective rim
    segment(-175 * u, -150 * u, 16 * u)
    segment(-150 * u, -85 * u, 24 * u)
    segment(-85 * u, 40 * u, 33 * u)
    segment(40 * u, 165 * u, 43 * u)
    segment(165 * u, 182 * u, 50 * u)

    # Tripod: three legs from the pivot point on the tube.
    leg_w = int(15 * u)
    pivot = (cx, cy)
    for end in ((0.24 * c, 0.90 * c), (0.52 * c, 0.91 * c), (0.71 * c, 0.83 * c)):
        d.line([pivot, end], fill=WHITE, width=leg_w)
    d.ellipse((cx - 26 * u, cy - 26 * u, cx + 26 * u, cy + 26 * u), fill=WHITE)

    # A small 4-point star up-left of the objective.
    sx, sy, r1, r2 = 0.80 * c, 0.20 * c, 34 * u, 10 * u
    star = []
    for i in range(8):
        r = r1 if i % 2 == 0 else r2
        a = math.pi / 4 * i - math.pi / 2
        star.append((sx + r * math.cos(a), sy + r * math.sin(a)))
    d.polygon(star, fill=WHITE)
    d.ellipse((0.68 * c - 8 * u, 0.34 * c - 8 * u,
               0.68 * c + 8 * u, 0.34 * c + 8 * u), fill=WHITE)

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    img.save(HERE / "app_icon.png")
    img.save(HERE / "app_icon.ico",
             sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("wrote app_icon.png and app_icon.ico")


if __name__ == "__main__":
    main()
