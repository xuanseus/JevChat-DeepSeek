# -*- coding: utf-8 -*-
"""聊天软件的 profile：截哪个窗口、哪个气泡算「我」说的。**目前只支持微信。**

下面几个字段是留给「以后加一个软件」的口子，但**加一个必须对着活窗口实测**：
气泡颜色、窗口选择、顶部的公告/置顶行都得量出来再填，别以为填个 exe 名就完事。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


def _wechat_me(bg: np.ndarray) -> bool:
    """WeChat's own bubble is green: G clearly above both R and B."""
    return bool(bg[1] > bg[0] + 40 and bg[1] > bg[2] + 40)


@dataclass(frozen=True)
class ChatApp:
    key: str
    label: str
    exes: tuple[str, ...]        # process names, lowercase
    main_title: str              # preferred top-level window title; "" = pick the biggest window
    skip_titles: tuple[str, ...]  # windows that are never a conversation (roster, toasts)
    is_me: Callable[[np.ndarray], bool]
    join: str = ""               # how OCR fragments inside one bubble are glued
    trim_top: Callable[[np.ndarray], int] = lambda chat: 0  # rows to skip (pinned notice, ...)


WECHAT = ChatApp("wechat", "微信", ("weixin.exe", "wechat.exe"), "微信", (), _wechat_me)

APPS = {a.key: a for a in (WECHAT,)}
DEFAULT = WECHAT


def by_exe(exe: str) -> ChatApp | None:
    return next((a for a in APPS.values() if exe in a.exes), None)


def get(key: str | None) -> ChatApp:
    return APPS.get(key or "", DEFAULT)


if __name__ == "__main__":  # 自测：颜色规则用实测像素锁住，改错了当场炸
    assert by_exe("weixin.exe") is WECHAT and by_exe("wechat.exe") is WECHAT
    assert by_exe("chrome.exe") is None and get(None) is DEFAULT and get("wechat") is WECHAT
    # 删掉的支持不许再认得出来——不然「支持微信」这句话就是假的
    assert by_exe("kakaotalk.exe") is None
    # 微信绿泡实测像素；白是面板底，黄是 KakaoTalk 的自己的泡，都不该判成自己的
    assert WECHAT.is_me(np.array((149, 236, 105)))
    assert not WECHAT.is_me(np.array((255, 255, 255)))
    assert not WECHAT.is_me(np.array((254, 229, 0)))
    assert WECHAT.trim_top(np.zeros((10, 10, 3), np.uint8)) == 0
    print("chatapps ok")
