# -*- coding: utf-8 -*-
"""盯微信头部：切会话时到底认不认得出新名字。

复刻 app/worker.py 里那条链路（settled → chat_area → 头部裁剪 → read_title），
但每一步都打出来。跑起来自己去微信切几次会话，对着日志看断在哪一环：

    PYTHONPATH=. .venv/Scripts/python.exe probe/probe_chat.py 90      # 盯 90 秒

PYTHONPATH=. 不能省：脚本在 probe/ 下，sys.path[0] 是 probe/ 而不是项目根，
直接跑会 ModuleNotFoundError: No module named 'app'。probe/ 下其它脚本同理。

三种断法在这里长得不一样：
  - 切了会话但一帧停稳帧都没有  → 出帧那关（Capture 的消息区 diff）没过
  - 有帧、头部 md5 没变         → 头部像素被判为没变，OCR 根本没跑
  - 有帧、变了但认不出/被并掉   → read_title / similar 那关的问题

readers 这个累积集合是 worker.py 里那份的等价物——similar() 是拿它去比的，
不累积就复现不出「新会话被并进旧会话」这个现象。
"""
import ctypes
import hashlib
import io
import sys
import time

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.capture import Capture, chat_area, find_chat_hwnd, unminimize
from app.ocr import _engine, read_title, similar


def main():
    ctypes.windll.user32.SetProcessDPIAware()
    hwnd, app = find_chat_hwnd()
    print(f"窗口 hwnd={hwnd}  app={app.key}", flush=True)
    cap = Capture(hwnd)
    readers = {}          # 等价于 worker.py 的 readers：见过哪些会话名
    title, head = "", None
    n = 0
    last_beat = time.time()
    t_end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 60)
    while time.time() < t_end:
        if not cap.alive():
            print("采集线程死了", flush=True)
            break
        unminimize(hwnd)
        full = cap.settled()
        if full is None:
            if time.time() - last_beat > 5:
                last_beat = time.time()
                print(f"  …已停稳 {n} 帧，这会儿没有新画面", flush=True)
            time.sleep(0.05)
            continue
        last_beat = time.time()
        n += 1
        area = chat_area(full)
        if area is None:
            print(f"[{n}] area=None —— 消息区认不出，整条链路跳过", flush=True)
            continue
        cap.area = area
        x0, y0, x1, y1, _bg, y_pane = area
        crop = full[y_pane:y0, x0:x1]
        changed = head is None or not np.array_equal(crop, head)
        old = title
        if changed:
            head = crop
            t0 = time.perf_counter()
            res, _ = _engine()(crop, use_cls=False)
            ms = (time.perf_counter() - t0) * 1000
            boxes = [(int(r[0][0][0]), int(r[0][0][1]), r[1]) for r in (res or [])]
            raw = read_title(crop, app)                      # 纯净的 OCR 结果
            # 这一步跟 worker.py:86 一模一样：拿已见过的会话名去套
            merged = next((k for k in readers if similar(k, raw)), None) if raw else None
            name = raw or title or "当前会话"
            readers.setdefault(name, None)
            title = name
            print(f"[{n}] 头部 {crop.shape} md5={hashlib.md5(np.ascontiguousarray(crop)).hexdigest()[:8]} "
                  f"变了 → OCR {ms:.0f}ms", flush=True)
            print(f"     框(top_y, x, 文字): {boxes}", flush=True)
            print(f"     read_title={raw!r}"
                  f"{f'  ← similar() 把它并到已有的 {merged!r}' if merged and merged != raw else ''}"
                  f"{'   ★ 会话变了' if title != old else '   （名字没变）'}", flush=True)
        else:
            print(f"[{n}] 头部 md5={hashlib.md5(np.ascontiguousarray(crop)).hexdigest()[:8]} "
                  f"没变 → 不跑 OCR（当前 {title!r}）", flush=True)
        time.sleep(0.05)
    print(f"结束：共 {n} 帧停稳，见过的会话 {list(readers)}", flush=True)


main()
