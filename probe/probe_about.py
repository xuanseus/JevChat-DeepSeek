# -*- coding: utf-8 -*-
"""验资料页（docs/wiki 那一页）的正文在窗口底色上读不读得清。

这类 bug 眼睛看不出来——打开一看像「空的」，其实是白字印白底，实测过一次
（深色系统下 Qt 调色板 Text 是 #ffffff，而这块底是 paintEvent 画的 #f4faf6，
对比度 1.05:1）。所以这里不靠看，直接渲染出来量 WCAG 对比度。

跑法：PYTHONPATH=. .venv/Scripts/python probe/probe_about.py
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.overlay import Overlay, _BG, _GREEN_TEXT, _BODY

# 一段有代表性的资料页：标题、二级标题、加粗、正文、列表——样式表里各选择器都覆盖到
SAMPLE = """# 我又不在意、

## 画像

**关系**：friends
**说话风格**：话少，几乎不用标点

**雷区**：别提他前任。

## 选择记录

- [2026-09-28 00:02] 第 1/3 条：我也是
- [2026-09-28 00:03] 第 2/3 条：行吧
"""

AA = 4.5  # WCAG AA 正文门槛


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(rgb):
    r, g, b = (_lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hexs(rgb):
    return "#%02x%02x%02x" % rgb


app = QApplication.instance() or QApplication([])
ov = Overlay(on_fill=lambda text: None)
ov.about.setMarkdown(SAMPLE)
ov.about.resize(420, 300)
ov.about.ensurePolished()

bg = tuple(int(_BG[i:i + 2], 16) for i in (1, 3, 5))
img = QImage(420, 300, QImage.Format_RGB32)
img.fill(QColor(_BG))  # 必须填成窗口底色：QTextBrowser 背景是透明的，不填就是在拿填充色当底去比
ov.about.render(img)

counts = {}
for y in range(300):
    for x in range(420):
        c = img.pixelColor(x, y)
        key = (c.red(), c.green(), c.blue())
        counts[key] = counts.get(key, 0) + 1

seen = max(counts.items(), key=lambda kv: kv[1])[0]
print(f"窗口底色 _BG = {_BG}   渲染后最多的颜色 = {hexs(seen)}")
if seen != bg:
    print(f"  底色对不上，说明控件自己画了底（或没渲染）——下面的数不可信")
    sys.exit(1)

# 正文色 = 去掉底色后出现最多的那几个（抗锯齿会散出一堆过渡色，笔画芯最集中；
# 中文还会走次像素渲染，同一笔能出好几种偏色，所以看「最清楚的一档」而不是某一个色）
ink = [(c, n) for c, n in counts.items() if c != seen and n >= 20]
if not ink:
    print("没量到任何文字像素——整页要么是空的，要么颜色跟底色一样（就是那个 bug）")
    sys.exit(1)
ink.sort(key=lambda kv: -kv[1])

print("\n出现最多的文字色（底色之上）：")
for c, n in ink[:4]:
    print(f"  {hexs(c)}  {n:5d} 像素   对底色 {contrast(c, seen):.2f}:1")

best = max(contrast(c, seen) for c, _ in ink)
print(f"\n最清楚的一档 = {best:.2f}:1   （_GREEN_TEXT={_GREEN_TEXT}  _BODY={_BODY}）")

if best < AA:
    print(f"\n不合格：正文对比度 {best:.2f}:1 低于 AA 的 {AA}:1，这页看着就是「空白」")
    sys.exit(1)
print(f"\n通过：{best:.2f}:1 ≥ AA {AA}:1")
