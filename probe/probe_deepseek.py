# -*- coding: utf-8 -*-
"""DeepSeek 探针：大模型能不能替 Jev 做判断/排序。

跟 probe_laya*.py 同一套 CASE、同一套题目，只是把 Laya 换成 DeepSeek。
作者的 Laya 结论是「不够稳，暂不替换」——那试的是 421M 小模型；大模型这条路是空白。

    set DEEPSEEK_API_KEY=sk-...
    PYTHONPATH=. python probe/probe_deepseek.py

只依赖 openai SDK，不需要 GUI 那一堆依赖。key 只从环境变量读，绝不落盘、绝不打印。
"""
from __future__ import annotations

import json
import os
import sys
import time
import types

from openai import OpenAI

from core.questions import JUDGE_QUESTIONS, build_rank_question, build_state

# probe_laya 顶部 import laya，而 Laya 没装（也不打算装）。
# 塞个空壳进 sys.modules，好复用它的 CASES——作者挑的那三段对话是这套探针的价值所在，不想抄一份。
if "laya" not in sys.modules:
    _stub = types.ModuleType("laya")
    _stub.load = lambda *a, **k: None  # type: ignore[attr-defined]
    sys.modules["laya"] = _stub

from probe.probe_laya import CASES, fmt  # noqa: E402

BASE_URL = "https://api.deepseek.com"
MODEL = os.environ.get("MODEL") or "deepseek-flash"
# 默认 high effort，判断一次要 5~14 秒。设 EFFORT=low 或 EFFORT=off 看能不能压下来。
EFFORT = (os.environ.get("EFFORT") or "").strip().lower()

SYSTEM = (
    "你是一个对话判断器。用户给你一段聊天记录和若干道结构化问题。"
    "你的任务不是回复聊天，只是逐题给出判断。"
    "必须严格按给定的 JSON 结构输出，不要输出任何解释、不要用 markdown 代码块包裹。"
)


def render_questions(questions: dict) -> str:
    """把题目 dict 渲染成人能读、模型能读的文字。"""
    lines = []
    for name, q in questions.items():
        qtype = q.get("type")
        lines.append(f"### 题目名：{name}（type={qtype}）")
        instructions = q.get("instructions")
        if instructions:
            lines.append(f"问题：{instructions}")
        criteria = q.get("criteria")
        if qtype == "noul":
            if isinstance(criteria, dict):
                if criteria.get("true"):
                    lines.append(f"  是（true）意味着：{criteria['true']}")
                if criteria.get("false"):
                    lines.append(f"  否（false）意味着：{criteria['false']}")
            lines.append('  输出：{"type":"noul","noul":<0~1 的概率，越接近 1 越是>}')
        elif qtype == "choice":
            lines.append("  可选项（必须原样引用标签名）：")
            for label, desc in (criteria or {}).items():
                lines.append(f"    - {label}：{desc}")
            lines.append('  输出：{"type":"choice","choice":"<选中的标签>","confidence":<0~1>,'
                         '"probabilities":{"<标签>":<0~1>, ...}}，所有选项都要给概率且和约等于 1')
        elif qtype == "score":
            lines.append("  评分档位（从 0 开始，逐档递增）：")
            for i, desc in enumerate(criteria or []):
                lines.append(f"    {i}：{desc}")
            lines.append('  输出：{"type":"score","score":<期望分，可以是小数>,"confidence":<0~1>,'
                         '"legend":{...照抄档位>},"probabilities":{"<档位>":<0~1>, ...}}')
        lines.append("")
    return "\n".join(lines)


def build_prompt(state: dict, questions: dict) -> str:
    chat = state["chat"]
    msgs = "\n".join(
        f"{'对方' if m['from'] == 'her' else '我'}"
        + (f"[{m['name']}]" if m.get("name") else "")
        + f"：{m['text']}"
        for m in chat["messages"]
    )
    return (
        f"【关系】{chat['relationship']}\n"
        f"【最新一句是】{'对方' if chat['latest_from'] == 'her' else '我'}说的\n"
        f"【对话】\n{msgs}\n\n"
        f"【要判断的题目】\n{render_questions(questions)}\n"
        '【输出格式】严格输出这样的 JSON，不要有别的内容：\n'
        '{"answers": {"<题目名>": {"type":"...", ...}, ...}}'
    )


def _effort_body() -> dict:
    """EFFORT=off 用项目起草那套关思考的写法；low/high/max 走 effort 档位。"""
    if EFFORT == "off":
        return {"thinking": {"type": "disabled"}}
    if EFFORT in ("low", "high", "max"):
        return {"effort": EFFORT}
    if EFFORT:
        raise SystemExit(f"EFFORT 只认 off/low/high/max，收到 {EFFORT!r}")
    return {}


def ask_deepseek(client: OpenAI, state: dict, questions: dict, timeout: float = 60) -> dict:
    """返回形状与 core.jev_client.ask() 完全一致，好直接对接 engine。"""
    started = time.perf_counter()
    kwargs = {}
    if body := _effort_body():
        kwargs["extra_body"] = body
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(state, questions)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        timeout=timeout,
        **kwargs,
    )
    elapsed = (time.perf_counter() - started) * 1000
    payload = json.loads(resp.choices[0].message.content)
    usage = resp.usage
    return {
        "answers": payload.get("answers") or {},
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        },
        "_ms": elapsed,
    }


# 作者在 CASES 的 expect 里写的口径，翻译成可判定的断言。
# 注意 B 的 expect 写的是「casual_chat / make_plan」，指的是 true_intent / best_action 两个字段。
CHECK = {
    "A 翻旧账": {
        "true_intent": ("confirm_you_care",), "best_action": ("check_history",),
        "danger_min": 4, "best_reply": "reply_a",
    },
    "B 约饭": {
        "true_intent": ("casual_chat",), "best_action": ("make_plan",),
        "danger_max": 2, "best_reply": "reply_a",
    },
    "C 炸了": {
        "true_intent": ("vent_anger",), "she_needs": ("care", "action"),
        "danger_min": 6, "best_reply": "reply_a",
    },
}


def check(case_name: str, answers: dict) -> list:
    spec = CHECK.get(case_name)
    if not spec:
        return []
    out = []
    for field in ("true_intent", "best_action", "she_needs", "best_reply"):
        if field not in spec:
            continue
        got = (answers.get(field) or {}).get("choice")
        ok = got in spec[field]
        out.append((field, ok, f"{got} ∈ {list(spec[field])}"))
    danger = (answers.get("danger_level") or {}).get("score")
    if "danger_min" in spec:
        out.append(("danger_level", isinstance(danger, (int, float)) and danger >= spec["danger_min"],
                    f"{danger} >= {spec['danger_min']}"))
    if "danger_max" in spec:
        out.append(("danger_level", isinstance(danger, (int, float)) and danger <= spec["danger_max"],
                    f"{danger} <= {spec['danger_max']}"))
    return out


def main() -> int:
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        print("!! 没设 DEEPSEEK_API_KEY", file=sys.stderr)
        return 2
    client = OpenAI(api_key=key, base_url=BASE_URL)

    total_ok = total = 0
    tokens = 0
    for name, rel, msgs, cands, expect in CASES:
        state = build_state(msgs, rel)
        print(f"\n{'=' * 72}\n--- {name}   期望：{expect}")

        # 第一次调用：7 道判断题（照 engine 的三段式）
        first = ask_deepseek(client, state, dict(JUDGE_QUESTIONS))
        answers = first["answers"]
        print(f"    [判断 {first['_ms']:.0f}ms]")
        for q, ans in answers.items():
            print(f"      {q:<18} {fmt(ans)}")

        # 第二次调用：只排序（engine 是在起草之后做的，这里候选是现成的）
        rank_q = build_rank_question(cands)
        second = ask_deepseek(client, state, rank_q)
        answers = {**answers, **second["answers"]}
        print(f"    [排序 {second['_ms']:.0f}ms]")
        for q, ans in second["answers"].items():
            print(f"      {q:<18} {fmt(ans)}")

        tokens += first["usage"]["input_tokens"] + first["usage"]["output_tokens"]
        tokens += second["usage"]["input_tokens"] + second["usage"]["output_tokens"]

        results = check(name, answers)
        if results:
            print("    判定：")
            for field, ok, detail in results:
                total += 1
                total_ok += 1 if ok else 0
                print(f"      {'PASS' if ok else 'FAIL'}  {field:<14} {detail}")

    print(f"\n{'=' * 72}")
    print(f"合计 {total_ok}/{total} 项通过；两轮共 {tokens} tokens")
    return 0 if total_ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
