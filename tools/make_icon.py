# -*- coding: utf-8 -*-
"""把 docs/icon.svg 转成 docs/icon.ico（打包用的程序图标）。

    python tools/make_icon.py

为什么要过一道 SVG：图标要出 16/32/48/64/128/256 六个尺寸，手写六份 PIL 画图代码没法维护。
SVG 写一份矢量源，逐个尺寸**原生渲染**——比「渲一张 256 再缩」清晰得多，
16px 下尤其明显（缩小会把细笔画糊掉）。

渲染器用 PySide6 的 QSvgRenderer，它本来就是依赖的一部分（spec 里也留着 QtSvg）。
不引 cairosvg 之类的新依赖，就为了转个图标不值当。

改图标 = 改 docs/icon.svg，然后重跑这个脚本。
"""
import io
import os
import struct
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "docs", "icon.svg")
OUT = os.path.join(ROOT, "docs", "icon.ico")
# **从大到小**。ICO 的条目顺序本身不影响 Windows 取哪张（它按需要的尺寸挑），
# 但资源管理器预览、IDE 的文件图标这些只显示第一条——从小到大排就显示 16×16，
# 看着像「这图标怎么这么糊」。见下面 write_ico。
SIZES = (256, 128, 64, 48, 32, 16)


def render(svg_path: str, size: int, png_path: str) -> None:
    """按尺寸原生渲染一张 PNG。"""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        raise SystemExit(f"SVG 读不了或不合规：{svg_path}")
    image = QImage(QSize(size, size), QImage.Format_ARGB32)
    image.fill(0)  # 先铺全透明，四角才不会带黑边
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    if not image.save(png_path, "PNG"):
        raise SystemExit(f"PNG 写不出去：{png_path}")


def write_ico(images, path: str) -> None:
    """自己拼 ICO，不用 Pillow 的 ico 写出。

    Pillow 的 IcoImagePlugin._save 会 `for size in sorted(sizes)`——**从小到大**。
    顺序本身不影响 Windows 取哪张（它按需要的尺寸挑），但资源管理器预览、PyCharm
    的文件图标这些只显示第一条，于是你看到的永远是 16×16，像没做高清图标一样。

    格式很简单：6 字节头（保留位、类型 1、条目数）+ 每条 16 字节目录 + 若干张 PNG 依次拼上。
    256 在宽高字段里写 0（一个字节放不下 256）。"""
    blobs = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blobs.append(buf.getvalue())
    entries, offset = b"", 6 + len(blobs) * 16
    for img, blob in zip(images, blobs):
        w, h = img.size
        entries += struct.pack("<BBBBHHII", w & 0xFF if w < 256 else 0,
                               h & 0xFF if h < 256 else 0,
                               0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<HHH", 0, 1, len(blobs)) + entries + b"".join(blobs))


def main() -> int:
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        pngs = []
        for size in SIZES:  # 已经从大到小
            path = os.path.join(tmp, f"{size}.png")
            render(SVG, size, path)
            pngs.append(Image.open(path).convert("RGBA"))
        write_ico(pngs, OUT)
    size = os.path.getsize(OUT)
    assert size > 1024, f"多尺寸 ico 不可能只有几百字节：{OUT} {size}"
    print(f"{OUT}  {size} bytes  {len(SIZES)} 个尺寸（大的在前）{SIZES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
