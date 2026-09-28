# -*- coding: utf-8 -*-
"""离屏验一下窗口是不是真的画了底色和圆角。grab() 会走一遍 paintEvent，量像素就知道。

跑法：PYTHONPATH=. .venv/Scripts/python .checkpaint.py
不进主循环、不联网、不读聊天，看一眼就退。
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication

from app.overlay import _BG as BG, Overlay
# 底色从常量取，不写字面量——换个主题色就得改一遍探针的话，这条检查迟早会被绕过。

app = QApplication.instance() or QApplication([])
ov = Overlay(on_fill=lambda text: None)
ov.win.resize(420, 720)
ov.win.show()
app.processEvents()

img = ov.win.grab().toImage()
w, h = img.width(), img.height()
print(f"尺寸 {w}x{h}")

# 正中间会压着卡片，那有它自己的颜色，不能拿它当「窗口底色」的采样点。
# 采窗口内衬边（圆角以内、内容以外）那一条，那里除了窗口底色不该有别的东西。
corner = img.pixelColor(1, 1)
edge = img.pixelColor(2, h // 2)
print(f"左上角 (1,1)      {corner.name()}  alpha={corner.alpha()}")
print(f"左内衬 (2,{h // 2})   {edge.name()}  alpha={edge.alpha()}")

ok = True
if edge.alpha() < 250:
    print("!! 窗口内衬是透明的——底色没画出来，这就是你看到的问题")
    ok = False
elif edge.name().lower() != BG:
    print(f"!! 内衬色不是窗口底色 {BG}，而是 {edge.name()}")
    ok = False
else:
    print("OK  窗口底色画上了")

if corner.alpha() > 200:
    print("!! 左上角还是实心的——圆角没生效")
    ok = False
else:
    print("OK  左上角是透的，圆角生效了")

ratio = w / h
print(f"宽高比 {ratio:.4f}（开窗基准 440/820 = {440 / 820:.4f}）")
if abs(ratio - 440 / 820) > 0.02:
    print("!! 等比缩放没锁住")
    ok = False
else:
    print("OK  等比缩放锁住了")

print("结论:", "通过" if ok else "有问题")
ov.win.close()
sys.exit(0 if ok else 1)
