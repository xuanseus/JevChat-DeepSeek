# -*- coding: utf-8 -*-
"""把 Claude Code 的会话记录（.jsonl）导成能读的 markdown，存进 docs/wiki/raw/chats/。

    python tools/archive_chat.py <session.jsonl> [输出路径]

会话文件一般在 `~/.claude/projects/<项目 slug>/<session-id>.jsonl`。

导出的原则：
- **用户和助手的正文原样保留**——那是「源对话」，wiki 的结论要能追溯回这里。
- 工具调用压成一行（工具名 + 摘要），工具返回整段丢掉。不压的话几万行 JSON 没人看得下去，
  而且文件里本来就有工具输出，没必要再存一份。
- **密钥一律打码。** 会话里会出现真实 API key（用户填的、或者被打印出来的），
  这份归档是要进 git 的，不脱敏就等于把 key 提交上去。宁可多打几个码。

自测：python tools/archive_chat.py --selftest   （拿合成数据验脱敏和渲染，不读磁盘）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 常见密钥形状 + 本机环境变量里真实存在的 key（后者兜底：形状认不出的也别漏）
_KEY_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),          # OpenAI / DeepSeek / OpenRouter …
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{8,}"),      # Anthropic
    re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"),        # Google
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),     # GitHub
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{12,}", re.I),
]
_KEY_ENVS = ("JEV_API_KEY", "LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
             "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def redact(text: str) -> str:
    """把密钥打码。先按环境变量里的真值精确替换，再按形状兜一遍。"""
    for name in _KEY_ENVS:
        value = (os.environ.get(name) or "").strip()
        if len(value) >= 8:
            text = text.replace(value, f"[REDACTED:{name}]")
    for pattern in _KEY_PATTERNS:
        text = pattern.sub("[REDACTED:key]", text)
    return text


def _blocks(content):
    """message.content 可能是字符串，也可能是 [{type: text|tool_use|tool_result|thinking}]。"""
    if isinstance(content, str):
        yield ("text", content)
        return
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            yield ("text", block.get("text") or "")
        elif kind == "tool_use":
            yield ("tool_use", (block.get("name") or "?", block.get("input") or {}))
        elif kind == "thinking":
            yield ("thinking", block.get("thinking") or "")


def _tool_summary(inputs) -> str:
    """一行说清这次工具调用在干嘛。Bash 取命令，别的取头几个参数。"""
    if not isinstance(inputs, dict):
        return ""
    for key in ("command", "file_path", "pattern", "query", "url", "prompt"):
        if inputs.get(key):
            one = " ".join(str(inputs[key]).split())
            return one[:160] + ("…" if len(one) > 160 else "")
    for key, value in list(inputs.items())[:2]:
        one = " ".join(f"{key}={value}".split())
        return one[:160] + ("…" if len(one) > 160 else "")
    return ""


def render(path: str) -> tuple[str, dict]:
    """→ (markdown, 统计)。只读该文件，不联网。"""
    turns: list[str] = []
    stats = {"user": 0, "assistant": 0, "tools": 0, "redacted": 0, "skipped": 0}
    first_ts, last_ts = "", ""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                stats["skipped"] += 1
                continue
            if row.get("type") not in ("user", "assistant"):
                continue
            msg = row.get("message")
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            stamp = str(row.get("timestamp") or "")
            if stamp:
                first_ts = first_ts or stamp
                last_ts = stamp
            head = "## 我" if role == "user" else "## Claude"
            body, tools = [], []
            for kind, payload in _blocks(msg.get("content")):
                if kind == "text" and payload.strip():
                    body.append(payload.strip())
                elif kind == "tool_use":
                    name, inputs = payload
                    summary = _tool_summary(inputs)
                    tools.append(f"`{name}` {summary}".strip())
                    stats["tools"] += 1
            if not body and not tools:
                continue  # 纯工具返回的那些行，丢掉
            chunk = [head]
            if body:
                chunk.append("\n\n".join(body))
            if tools:
                chunk.append("> 工具：" + "；".join(tools))
            turns.append("\n\n".join(chunk))
            stats[role] += 1

    text = redact("\n\n".join(turns))
    stats["redacted"] = text.count("[REDACTED")
    header = [
        f"# 对话归档 · {os.path.basename(path)}",
        "",
        f"- 来源：`{path}`",
        f"- 时间：{first_ts or '?'} → {last_ts or '?'}",
        f"- 轮次：用户 {stats['user']} / 助手 {stats['assistant']}，工具调用 {stats['tools']} 条（只留一行摘要）",
        "",
        "> 工具返回的内容已丢弃，密钥已打码。要还原细节请看原始 jsonl。",
        "",
        "---",
        "",
    ]
    return "\n".join(header) + text + "\n", stats


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    text, stats = render(src)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"已写入 {out}")
    else:
        print(text)
    print(f"用户 {stats['user']} / 助手 {stats['assistant']} / 工具 {stats['tools']} / 打码 {stats['redacted']}")
    return 0


def _selftest() -> int:
    import tempfile

    rows = [
        {"type": "user", "timestamp": "2026-09-28T10:00:00Z",
         "message": {"role": "user", "content": "key 是 sk-FAKEONLY000000000000000000 别外传"}},
        {"type": "assistant", "timestamp": "2026-09-28T10:00:05Z",
         "message": {"role": "assistant", "content": [
             {"type": "thinking", "thinking": "不该出现"},
             {"type": "text", "text": "好。"},
             {"type": "tool_use", "name": "Bash", "input": {"command": "curl -H 'Authorization: Bearer abcdefghijklmnop' x"}},
         ]}},
        {"type": "user", "message": {"role": "user", "content": [
             {"type": "tool_result", "content": "一大坨工具返回"}]}},
        {"type": "mode", "message": {}},
    ]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl",
                                     delete=False) as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        path = fh.name
    try:
        text, stats = render(path)
    finally:
        os.unlink(path)

    # 断言「打码后一个 sk- 都不剩」，而不是比对某个具体串——原来这里写的是某个真 key 的
    # 前 7 位，等于把密钥片段钉进了仓库，而这个测试本身根本不需要它。
    assert "sk-" not in text, "API key 没打掉"
    assert "sk-ant-" not in text and "abcdefghijklmnop" not in text, "Bearer 没打掉"
    assert "[REDACTED" in text
    assert "不该出现" not in text, "thinking 不该导出"
    assert "一大坨工具返回" not in text, "工具返回不该导出"
    assert "## 我" in text and "## Claude" in text
    assert "`Bash` curl" in text, "工具调用该留一行摘要"
    assert stats == {"user": 1, "assistant": 1, "tools": 1, "redacted": 2, "skipped": 0}, stats
    print("archive_chat selftest ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
