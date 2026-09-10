#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 themes/default/pet.png —— 一个原创的中性吉祥物（麻薯团子抱着书）。

只有想重新生成默认形象时才需要跑，需要 Pillow：
    pip install Pillow
    python3 tools/make_default_pet.py
换成自己的图片时不需要它，直接替换 themes/<主题>/pet.png 即可（PNG 透明背景）。
"""
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow")

S = 4                      # 超采样倍数，画大后缩小得到抗锯齿边缘
W = H = 512                # 最终尺寸
BODY = (246, 231, 206, 255)
LINE = (138, 117, 99, 255)
EAR = (240, 201, 168, 255)
EYE = (59, 47, 40, 255)
BLUSH = (242, 166, 160, 110)
COVER = (78, 156, 138, 255)
PAGE = (255, 253, 246, 255)
LW = 5 * S                 # 线宽


def rr(d, box, r, fill, outline=LINE, width=LW):
    d.rounded_rectangle([v * S for v in box], radius=r * S,
                        fill=fill, outline=outline, width=width)


def el(d, box, fill, outline=None, width=LW):
    d.ellipse([v * S for v in box], fill=fill, outline=outline, width=width)


def main():
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 耳朵（先画，被身体压住下缘）
    for cx in (168, 344):
        el(d, (cx - 34, 120, cx + 34, 205), BODY, LINE)
        el(d, (cx - 17, 143, cx + 17, 190), EAR)

    # 身体：一整块麻薯，头身不分
    rr(d, (110, 150, 402, 432), 132, BODY)

    # 脚
    for cx in (196, 316):
        el(d, (cx - 36, 402, cx + 36, 446), BODY, LINE)

    # 眼睛 + 高光
    for cx in (208, 304):
        el(d, (cx - 21, 246, cx + 21, 296), EYE)
        el(d, (cx - 8, 256, cx + 4, 270), (255, 255, 255, 235))

    # 腮红
    for cx in (156, 356):
        el(d, (cx - 26, 300, cx + 26, 326), BLUSH)

    # 嘴：两段小弧
    d.arc([(238) * S, (300) * S, (256) * S, (320) * S], 20, 160, EYE, LW)
    d.arc([(256) * S, (300) * S, (274) * S, (320) * S], 20, 160, EYE, LW)

    # 抱着的书
    d.polygon([(v * S) for p in
               [(150, 372), (256, 352), (362, 372), (362, 428), (256, 408), (150, 428)]
               for v in p], fill=PAGE, outline=LINE)
    d.line([(256 * S, 352 * S), (256 * S, 408 * S)], fill=LINE, width=LW)
    d.line([(150 * S, 428 * S), (256 * S, 408 * S), (362 * S, 428 * S)],
           fill=COVER, width=int(LW * 2.2))
    for y in (382, 396):                      # 书页上的两行"字"
        d.line([(178 * S, y * S), (236 * S, (y - 4) * S)], fill=LINE, width=int(LW * 0.6))
        d.line([(276 * S, (y - 4) * S), (334 * S, y * S)], fill=LINE, width=int(LW * 0.6))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "themes", "default", "pet.png")
    img.resize((W, H), Image.LANCZOS).save(os.path.normpath(out))
    print("已生成", os.path.normpath(out))


if __name__ == "__main__":
    main()
