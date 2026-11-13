# -*- coding: utf-8 -*-
"""生成应用图标 app.ico（大肥鱼），只用标准库 + Pillow（仅打包时用一次，运行不需要）。"""
import os

from PIL import Image, ImageDraw

SIZE = 256
BG = (251, 246, 234, 0)
FISH = (245, 161, 94, 255)
FISH_D = (218, 130, 68, 255)
INK = (59, 50, 42, 255)
BLUSH = (247, 168, 184, 200)
CREAM = (255, 253, 246, 255)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角底板（手账纸色）
d.rounded_rectangle([6, 6, SIZE - 6, SIZE - 6], radius=56, fill=(251, 246, 234, 255),
                    outline=INK, width=8)

# 尾巴
d.polygon([(176, 128), (232, 92), (222, 128), (232, 164)], fill=FISH_D)
# 身体
d.ellipse([52, 72, 190, 186], fill=FISH, outline=INK, width=7)
# 肚子浅色
d.ellipse([66, 120, 176, 180], fill=(255, 192, 139, 255))
# 眼睛
d.ellipse([92, 96, 124, 128], fill=CREAM, outline=INK, width=5)
d.ellipse([100, 104, 116, 120], fill=INK)
d.ellipse([104, 107, 110, 113], fill=CREAM)
# 腮红
d.ellipse([68, 132, 92, 152], fill=BLUSH)
# 嘴
d.arc([104, 138, 140, 164], start=10, end=170, fill=INK, width=6)
# 鳞片
for x, y in ((142, 100), (158, 118), (140, 138), (158, 152)):
    d.ellipse([x, y, x + 16, y + 16], outline=(218, 130, 68, 180), width=4)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("已生成图标：", out)
