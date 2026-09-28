# -*- coding: utf-8 -*-
"""找聊天窗口 + Windows Graphics Capture 盯着它 + 从帧里定位消息区。帧全程内存，绝不落盘。"""
import ctypes
import os
import time
from ctypes import wintypes

import numpy as np

from app import chatapps

u32 = ctypes.windll.user32


def find_chat_hwnd(want=None):
    """枚举可见顶层窗口，按进程名认出聊天软件，返回 (hwnd, ChatApp)。
    微信：同进程还有工具窗和看图窗，面积可能更大，所以按标题挑主窗口。
    want=某个 ChatApp 时只找它，None 时按 APPS 顺序取第一个认出来的。"""
    k32 = ctypes.windll.kernel32
    found = []

    def exe_of(pid):
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        buf, size = ctypes.create_unicode_buffer(1024), ctypes.c_uint(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        k32.CloseHandle(h)
        return os.path.basename(buf.value).lower() if ok else ""

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        if not u32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        app = chatapps.by_exe(exe_of(pid.value))
        if app and (want is None or app is want):
            title = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(hwnd, title, 256)
            rect = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rect))
            area = (rect.right - rect.left) * (rect.bottom - rect.top)
            found.append((hwnd, title.value, area, app))
        return True

    u32.EnumWindows(cb, 0)
    if not found:
        raise RuntimeError("没找到聊天窗口，开着吗？")
    for app in chatapps.APPS.values():
        mine = [f for f in found if f[3] is app]
        if not mine:
            continue
        if app.main_title:
            hit = next((f for f in mine if f[1] == app.main_title), None)
            if hit:
                return hit[0], app
        rooms = [f for f in mine if f[1] not in app.skip_titles] or mine
        best = max(rooms, key=lambda f: f[2])
        return best[0], app
    raise RuntimeError("没找到聊天窗口，开着吗？")


def find_wechat_hwnd():
    """老名字：只返回 hwnd，给还没改过来的调用方用。"""
    return find_chat_hwnd()[0]


def _panel_divider(full, col, lim):
    """左边会话列表和右边聊天面板之间那根竖分隔线的 x，找不到返回 None。

    判据跟下面找横向分隔线一样，只是竖过来：整列单色（上下没有变化 = 是一条线，不是内容）
    且不是面板底色。x 按 2 下采样算，返回时乘回去。
    lim = 只认这根线左边的候选，免得把面板内部某个竖边（宽图片、选中高亮）当成栏分界。"""
    band = full[full.shape[0] // 4: full.shape[0] * 3 // 4:4, ::2].astype(int)
    single = band.std(axis=(0, 2)) < 4
    hits = np.where(single & (col[::2] < 0.1) & (np.arange(single.size) * 2 < lim))[0] * 2
    return int(hits[-1]) if hits.size else None


def unminimize(hwnd):
    """Windows 不渲染最小化的窗口，什么截图法都拿不到画面。发现被最小化就无激活还原，再压到所有窗口最底下——
    看着跟收起来一样，但 DWM 继续画。不抢焦点、不动大小位置。返回是否动了手。"""
    if not u32.IsIconic(hwnd):
        return False
    u32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
    u32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x13)  # HWND_BOTTOM, SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE
    return True


def chat_area(full, header_h=60):
    """消息列表区 (x0, y_top, x1, y_in, 面板底色, y_pane)，全靠像素锚点，不写死坐标，深浅主题通用：
    - 面板底色 = 右半边最常见的颜色（抽样算，全量 np.unique 在 2560 宽的图上要半秒）
    - 面板左/右边界 = 第一/最后一根「底色占比 > 30%」的列（联系人列表是另一种底色，占比 0）；
      两栏底色一样时这几列会落到窗口最左边，所以再找一次两栏之间的竖分隔线把左边收回来
    - y_pane = 面板第一行；会话名就印在 y_pane~y_top 这条头部里（公告条也在里面）
    - 横向分隔线 = 整行单色且非底色；输入框顶 y_in = 面板 45% 高度以下第一根；
      公告条下面那根（有的话）= 消息区顶 y_top，没有就用 header_h
    认不出（窗口太小 / 拖到一半布局没铺好）返回 None。
    ponytail: 输入框拉高超过面板一半会认错；header_h 按 100% DPI 给的，缩放了按比例调。"""
    H, W = full.shape[:2]
    right = full[::8, W // 2::8].reshape(-1, 3)
    vals, cnt = np.unique(right, axis=0, return_counts=True)
    bg = vals[cnt.argmax()]
    isbg = np.abs(full.astype(int) - bg).sum(-1) <= 6
    col = isbg[H // 4: H * 3 // 4].mean(0)
    x0 = int(np.argmax(col > 0.3))
    x1 = W - int(np.argmax(col[::-1] > 0.3))
    # 两栏底色一样时（浅色主题常见）上面那行会把整个会话列表框进来——左边那些列同样
    # 满足「底色占比 > 30%」。补一道正信号：两栏之间那根竖分隔线。只在它比 x0 更靠右时
    # 才收（说明确实框多了），找不到线就完全保持原样，不影响本来正常的主题。
    divider = _panel_divider(full, col, int(0.65 * x1))
    if divider is not None and x1 - divider >= 200:
        x0 = max(x0, divider)
    row = isbg[:, x0:x1].mean(1)
    y0 = int(np.argmax(row > 0.9))
    y1 = H - int(np.argmax(row[::-1] > 0.9))
    band = full[y0:y1, x0:x1].astype(int)
    seps = y0 + np.where((band.std(axis=(1, 2)) < 4) & (row[y0:y1] < 0.1))[0]
    seps = [int(s) for i, s in enumerate(seps) if i == 0 or s - seps[i - 1] > 3]
    below = [s for s in seps if s > y0 + 0.45 * (y1 - y0)]
    y_in = below[0] if below else y1
    above = [s for s in seps if y0 + header_h < s < y_in - 50]
    y_top = above[-1] if above else y0 + header_h
    if x1 - x0 < 100 or y_in - y_top < 40:
        return None
    return x0, y_top, x1, y_in, bg, y0


class Capture:
    """WGC 盯窗口。采集线程只做「跟上一帧比」；settled() 在画面停稳后交出整帧，中间帧（滚动动画、
    新消息滑入的半截气泡）全跳过。动图表情永远停不稳，所以最多等 max_wait 秒照样交。"""

    def __init__(self, hwnd, settle=0.25, max_wait=1.0):
        from windows_capture import WindowsCapture

        self.settle, self.max_wait = settle, max_wait
        self.shape = self.area = self.last = self.pending = None
        self.t = self.t0 = 0.0
        # 包装层默认 cursor_capture=True，会去调 SetIsCursorCaptureEnabled。
        # 这个属性要 Win10 2004（build 19041）才有，1909 及更早直接抛 CursorConfigUnsupported。
        # 显式 None 走系统默认，不去切换；draw_border 同理。
        cap = WindowsCapture(cursor_capture=None, draw_border=None, window_hwnd=hwnd)
        cap.event(self.on_frame_arrived)
        cap.event(self.on_closed)
        self.ctl = cap.start_free_threaded()

    def on_frame_arrived(self, frame, control):
        full = np.ascontiguousarray(frame.frame_buffer[:, :, :3][:, :, ::-1])  # BGRA → RGB；缓冲区回调后就没了，必须拷
        if full.max() == 0:
            return
        if self.area is None or full.shape != self.shape:
            self.shape, self.area = full.shape, chat_area(full)
        if self.area is None:
            return
        x0, y0, x1, y1 = self.area[:4]  # 拿上一次的消息区做 diff 就够了，光标闪烁在输入框里，不算变化
        # ponytail: diff 不含头部——公告条会滚动，带上它就永远停不稳。切会话时消息区必然也变，照样出帧。
        chat = full[y0:y1, x0:x1]
        if self.last is not None and np.array_equal(chat, self.last):
            return
        self.last = chat
        if self.pending is None:
            self.t0 = time.perf_counter()
        self.pending, self.t = full, time.perf_counter()

    def on_closed(self):
        pass

    def settled(self):
        """停稳了就返回整帧，否则 None。"""
        if self.pending is None:
            return None
        now = time.perf_counter()
        if now - self.t < self.settle and now - self.t0 < self.max_wait:
            return None
        full, self.pending = self.pending, None
        return full

    def alive(self):
        return not self.ctl.is_finished()

    def stop(self):
        self.ctl.stop()

    def wait(self):
        self.ctl.wait()  # 采集线程若是报错死的，这里把错误抛出来


if __name__ == "__main__":
    # ponytail: 合成假窗口验 chat_area 的左边界。真帧拿不到（帧不落盘，也不该落），
    # 所以只验几何判据本身——会坏的地方就两个：两栏同色时收不收得回来，正常时别乱动。
    W, H, SPLIT, WALL = 1200, 800, 300, (150, 150, 150)

    def frame(list_bg, panel_bg, *, divider=True, inner_edge=None):
        f = np.zeros((H, W, 3), dtype=np.uint8)
        f[:, :SPLIT] = list_bg
        f[:, SPLIT:] = panel_bg
        if divider:
            f[:, SPLIT - 2:SPLIT] = WALL          # 两栏之间那根竖线
        f[600:602, :] = WALL                      # 输入框上方那根横线，用来定 y_in
        f[200:260, SPLIT + 40:SPLIT + 300] = (95, 190, 120)   # 一个绿气泡
        if inner_edge is not None:                # 面板内部另一根竖线（宽图片边缘之类）
            f[:, inner_edge:inner_edge + 2] = WALL
        return f

    WHITE = (255, 255, 255)
    GREY = (240, 240, 240)

    # 两栏底色不同（作者原本假设的情形）：左边界本来就对，别动它
    area = chat_area(frame(GREY, WHITE))
    assert area is not None and area[0] == SPLIT, area
    assert area[2] == W and area[1] == 60 and area[3] == 600, area

    # 两栏底色相同（浅色主题）：原来 x0 会落到 0，把整个会话列表框进来；现在该收到竖线上
    area = chat_area(frame(WHITE, WHITE))
    assert area is not None and area[0] == SPLIT - 2, area

    # 没有竖线可认时不许乱猜：保持原样（可能仍框多了，但不比改之前差）
    area = chat_area(frame(WHITE, WHITE, divider=False))
    assert area is not None and area[0] == 0, area

    # 面板内部的竖边不能被当成栏分界（它在 0.65*x1 右边，直接排除）
    area = chat_area(frame(WHITE, WHITE, inner_edge=1000))
    assert area is not None and area[0] == SPLIT - 2, area

    # 窗口太窄（面板不足 100px）就该返回 None，加了竖线判据不能把它救回来
    assert chat_area(np.zeros((300, 80, 3), dtype=np.uint8)) is None
    print("capture ok")
