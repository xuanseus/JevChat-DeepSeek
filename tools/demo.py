# -*- coding: utf-8 -*-
"""端到端冒烟：截图里那段真实对话跑一遍完整链，打印判断 + 排好序的候选。

链路是三段式：Jev 判断（7 道题） → 带着判断起草 3 条 → Jev 排序，两次 Jev 调用。

全程只要两把 key：判断一把 JEV_API_KEY（OpenRouter 或 TypeSafe 的），起草一把 LLM_API_KEY。

    set JEV_API_KEY=...   &  set LLM_API_KEY=...    (Windows)
    export JEV_API_KEY=... && export LLM_API_KEY=...(mac/Linux)
    python tools/demo.py

默认：判断走 DeepSeek，起草走 DeepSeek 官网直连（本 fork 判断不用 Jev）。
换来源用环境变量 JEV_PROVIDER / DRAFT_PROVIDER（可选的见 core/providers.py 的两张表），
两把 key 填同一个值即可。
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.engine import analyze
from core.jev_client import JevError
from core.questions import guidance_text

_SPEAKERS = {"我": "me", "她": "her", "他": "her", "对方": "her"}
_RELATION_KEYS = ("关系", "关系：", "关系:")
_SEP = "："


def parse_conversation(text: str) -> tuple[list[tuple[str, str]], str]:
    """吃手敲的对话，返回 (messages, relationship)。

    一行一句，形如「关系：朋友」/「我：…」/「她：…」；中英文冒号都认，
    他/对方 一律当 her。认不出的行直接跳过，不做猜测——宁可少几行也别弄错说话人。
    """
    messages: list[tuple[str, str]] = []
    relationship = RELATIONSHIP
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head, sep, rest = line.partition(_SEP)
        if not sep:
            head, sep, rest = line.partition(":")
        if not sep:
            continue
        head, rest = head.strip(), rest.strip()
        if head in _RELATION_KEYS:
            if rest:
                relationship = rest
        elif head in _SPEAKERS and rest:
            messages.append((_SPEAKERS[head], rest))
    return messages, relationship

MESSAGES = [
    ("her", "你今天是不是又忘了我跟你说过什么？"),
    ("me", "记得，你先别提示我，让我自己说。"),
    ("her", "那你说。"),
    ("me", "等一下，我想说完整一点。"),
    ("her", "你最好是。"),
]
RELATIONSHIP = "romantic partners"
PROVIDER = os.environ.get("DRAFT_PROVIDER") or "deepseek"  # 起草来源，见 core.providers.DRAFT_PROVIDERS
# 判断来源（见 core.providers.JEV_PROVIDERS）。本 fork 只有 deepseek 一条，用环境变量试别的。
JEV_PROVIDER = os.environ.get("JEV_PROVIDER") or "deepseek"


def fmt(name: str, ans: dict) -> str:
    t = ans.get("type")
    if t == "noul":
        return f"{name}: {ans.get('noul'):.2f}"
    if t == "choice":
        return f"{name}: {ans.get('choice')} (conf {ans.get('confidence'):.2f})"
    if t == "score":
        return f"{name}: {ans.get('score'):.1f}/9 (conf {ans.get('confidence'):.2f})"
    return f"{name}: {ans}"


def main() -> int:
    # 给了文件就用手敲的那段对话（格式见 parse_conversation），否则跑内置那段
    messages, relationship = MESSAGES, RELATIONSHIP
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], encoding="utf-8") as fh:
                messages, relationship = parse_conversation(fh.read())
        except OSError as e:
            print(f"读不了 {sys.argv[1]}: {e}")
            return 2
        if len(messages) < 2:
            print(f"{sys.argv[1]} 里没解析出对话，格式是「我：…」「她：…」，至少两条")
            return 2
        if messages[-1][0] != "her":
            print("提醒：最后一条不是对方说的。程序是靠对方冒出新消息触发的，"
                  "判断结果仅供参考。")

    print("对话:")
    for w, t in messages:
        print(f"  {w}: {t}")
    print(f"关系: {relationship}")
    try:
        r = analyze(messages, relationship, provider=PROVIDER, jev_provider=JEV_PROVIDER)
    except JevError as e:
        print(f"\n失败: {e}")
        return 1

    print("\n判断:")
    for name in ("literal_question", "true_intent", "danger_level",
                 "should_reply_now", "best_action", "she_needs", "tension_resolved"):
        if name in r["answers"]:
            print("  " + fmt(name, r["answers"][name]))

    block = guidance_text(r["answers"])  # 起草时喂进去的那张小抄
    if block:
        print("\n" + block)

    print("\n候选（模型排序，★ = 推荐）:")
    scores = r.get("scores")
    reasons = r.get("reasons") or []
    for i, c in enumerate(r["candidates"]):
        pct = f"  {scores[i]:.0%}" if scores else ""
        print(f"  {'★' if i == r['best_index'] else ' '} {c}{pct}")
        if i < len(reasons) and reasons[i]:
            print(f"      └ {reasons[i]}")

    u = r["usage"]
    if u:
        print(f"\nusage: in={u.get('input_tokens')} out={u.get('output_tokens')} "
              f"cost=${u.get('cost')}")
    if len(sys.argv) == 1:  # 只有跑内置那段才有标准答案可对
        print("\n期望核对: true_intent≈confirm_you_care, best_action≈check_history, "
              "danger_level 中高档")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
