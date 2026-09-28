# -*- coding: utf-8 -*-
"""判断 API 客户端：把题库渲染成提示词，让 OpenAI 兼容的大模型逐题作答再解析回 JSON。

走 core/llm.chat()（项目约定各协议用官方 SDK，不自己拼 HTTP），返回 engine 认的
{"answers": {...}, "usage": {...}} 形状。key 只从环境变量读，绝不打进日志。

上游还有「OpenRouter / TypeSafe 直连」两条走 Jev 专用决策接口的路，本 fork 去掉了
（判断改用通用大模型，不用再申请 Jev 的 key）。要加回来就得自己拼 HTTP——typesafe_sdk
把路径写死成 /v1/systemone，打不到 OpenRouter 的 /api/alpha/decisions。
"""

from __future__ import annotations

import json
import os
from typing import NoReturn

try:  # 当模块导入 / 当脚本直接跑 都能用
    from .providers import (ENV_VARS, JEV_BASE_ENV, JEV_ENV, JEV_PROVIDERS, LEGACY,
                            LLM_ENV)
except ImportError:
    from providers import (ENV_VARS, JEV_BASE_ENV, JEV_ENV, JEV_PROVIDERS, LEGACY,
                           LLM_ENV)

# 一次要答 7 道题 + 排序题，每道都带概率分布；llm.chat 默认的 400 会截断。
JUDGE_MAX_TOKENS = 4000


class JevError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def redact_secrets(text: str) -> str:
    """Strip every live key from any string before print or disk write."""
    if not isinstance(text, str):
        text = str(text)
    for env in ENV_VARS:
        key = os.environ.get(env) or ""
        if key:
            text = text.replace(key, "[REDACTED]")
    return text


def _status_of(exc: Exception) -> int | None:
    """各家 SDK 放 HTTP 状态码的属性名不一样：openai/anthropic 是 status_code，
    google-genai 是 code（它的 status 是 'NOT_FOUND' 这种字符串），typesafe 是 status。"""
    for name in ("status_code", "code", "status"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    return None


def _fail(exc: Exception, what: str) -> NoReturn:
    """SDK 抛的异常 → 一句人话的 JevError。消息过脱敏，绝不把 key 带出来。"""
    if isinstance(exc, JevError):
        raise exc
    status = _status_of(exc)
    hint = {401: "密钥被拒", 403: "没有权限", 404: "模型或地址不对", 422: "请求被拒",
            429: "被限流", 529: "服务过载"}.get(status, "")
    detail = redact_secrets(str(exc)).strip()[:300]
    head = f"{what} HTTP {status}" if status else f"{what}失败"
    raise JevError(f"{head}: {hint or detail or type(exc).__name__}", status) from None


# 设置文件里的 key 由调用方注入：桌面端从 config.json 读，命令行脚本不一定注入。
# core 不该知道配置文件在哪，所以只留一个回调。
_key_source = None


def set_key_source(source) -> None:
    """source(env_name) -> str。app 启动时注入 app.settings.key_of。"""
    global _key_source
    _key_source = source


def _api_key(env: str = JEV_ENV) -> str:
    """两把 key 之一（JEV_API_KEY / LLM_API_KEY）。

    **优先环境变量，其次才是设置文件里填的。** 这么排是因为程序自己不再写环境变量了，
    环境里如果有，只可能是用户自己放的——那多半就是想临时盖掉设置里那个跑一次。
    老名字（OPENROUTER_API_KEY / DEEPSEEK_API_KEY）也算环境变量这一档。"""
    key = ((os.environ.get(env) or "").strip()
           or (os.environ.get(LEGACY.get(env, "")) or "").strip())
    if not key and _key_source is not None:
        key = (_key_source(env) or "").strip()
    if not key:
        raise JevError(f"{env} 没配置。打开设置页在「模型」卡片里填，或者用环境变量临时指定。")
    return key


def ask(state: dict, questions: dict, timeout: float = 20,
        provider: str = "deepseek", model: str | None = None) -> dict:
    """问判断模型一轮，返回 {"answers": {名字: 答案}, "usage": {...}}。

    provider ∈ JEV_PROVIDERS；model=None 用该来源的默认模型。绝不打印或写出 key。
    """
    spec = JEV_PROVIDERS.get(provider) or next(iter(JEV_PROVIDERS.values()))
    key = _api_key(JEV_ENV)  # 各家共用同一把 key，换来源不用重填
    model = model or spec.default
    base = (os.environ.get(JEV_BASE_ENV) or "").strip() or spec.base
    # 换了地址就别带 extra：思考开关是 DeepSeek 自家的字段，别的端点不认
    extra = spec.extra if base == spec.base else None
    return _ask_compatible(state, questions, key, model, base, extra, timeout)


def render_questions(questions: dict) -> str:
    """题库 → 给顶替模型看的题面。criteria 的标签名原样带出去，答案要按标签回来。"""
    lines: list[str] = []
    for name, question in questions.items():
        qtype = question.get("type")
        lines.append(f"### 题目名：{name}（type={qtype}）")
        instructions = question.get("instructions")
        if instructions:
            lines.append(f"问题：{instructions}")
        criteria = question.get("criteria")
        if qtype == "noul":
            if isinstance(criteria, dict):
                if criteria.get("true"):
                    lines.append(f"  是（true）意味着：{criteria['true']}")
                if criteria.get("false"):
                    lines.append(f"  否（false）意味着：{criteria['false']}")
            lines.append('  输出：{"type":"noul","noul":<0~1 的概率，越接近 1 越肯定为「是」>}')
        elif qtype == "choice":
            lines.append("  可选项（choice 必须原样引用标签名）：")
            for label, desc in (criteria or {}).items():
                lines.append(f"    - {label}：{desc}")
            lines.append('  输出：{"type":"choice","choice":"<选中的标签>","confidence":<0~1>,'
                         '"probabilities":{"<标签>":<0~1>, …}}，每个选项都要给概率且和约等于 1')
        elif qtype == "score":
            lines.append("  评分档位（从 0 开始，逐档递增）：")
            for i, desc in enumerate(criteria or []):
                lines.append(f"    {i}：{desc}")
            lines.append('  输出：{"type":"score","score":<期望分，可以是小数>,"confidence":<0~1>,'
                         '"legend":{…照抄档位>},"probabilities":{"<档位>":<0~1>, …}}')
        lines.append("")
    return "\n".join(lines)


def _judge_prompt(state: dict, questions: dict) -> str:
    chat = state.get("chat") or {}
    messages = chat.get("messages") or []
    transcript = "\n".join(
        ("对方" if m.get("from") == "her" else "我")
        + (f"[{m['name']}]" if m.get("name") else "")
        + f"：{m.get('text', '')}"
        for m in messages
    )
    return (
        f"【关系】{chat.get('relationship', '')}\n"
        f"【最新一句是】{'对方' if chat.get('latest_from') == 'her' else '我'}说的\n"
        f"【对话】\n{transcript}\n\n"
        f"【要判断的题目】\n{render_questions(questions)}\n"
        "【输出格式】严格输出这样的 JSON，不要有别的内容：\n"
        '{"answers": {"<题目名>": {"type": "…", …}, …}}'
    )


def _parse_judge_json(text: str) -> dict:
    """模型输出 → answers dict。response_format 已经要了 JSON，但个别端点不认这个参数，
    会拿 ```json 包一层，所以这里再剥一次围栏。"""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError) as exc:
        raise JevError(f"判断模型返回的不是 JSON：{redact_secrets(str(exc))[:200]}") from None
    if not isinstance(payload, dict):
        raise JevError("判断模型返回的 JSON 顶层不是对象")
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevError("判断模型返回的 JSON 里没有 answers 对象")
    return answers


def _ask_compatible(state: dict, questions: dict, key: str, model: str,
                    base: str, extra, timeout: float) -> dict:
    """OpenAI 兼容的大模型顶替判断。走 core/llm.chat()，错误已在那边转成 JevError。

    这里的 usage 拿不到（llm.chat 只回文本），返回空 dict——engine 的 _add_usage 容得下空，
    只是界面上不显示顶替判断那部分的 token。"""
    try:
        from .llm import chat as llm_chat
    except ImportError:
        from llm import chat as llm_chat

    text = llm_chat("openai", base, key, model, _JUDGE_SYSTEM,
                    [_judge_prompt(state, questions)],
                    temperature=0.0, max_tokens=JUDGE_MAX_TOKENS,
                    extra_body=extra() if extra else None,
                    timeout=timeout,
                    response_format={"type": "json_object"})
    return {"answers": _parse_judge_json(text), "usage": {}}


_JUDGE_SYSTEM = (
    "你是一个对话判断器。用户给你一段聊天记录和若干道结构化问题。"
    "你的任务不是回复聊天，只是逐题给出判断，按给定标签作答、按给定档位打分。"
    "必须严格按指定的 JSON 结构输出，不要解释、不要用 markdown 代码块包裹。"
)



def list_models(provider: str, key: str, timeout: float = 10) -> list[str]:
    """这个来源上能用的模型 id，去重排序。失败抛 JevError（设置页直接显示这句话）。"""
    try:
        from .llm import list_models as llm_list_models
    except ImportError:
        from llm import list_models as llm_list_models

    spec = JEV_PROVIDERS.get(provider) or next(iter(JEV_PROVIDERS.values()))
    base = (os.environ.get(JEV_BASE_ENV) or "").strip() or spec.base
    return llm_list_models("openai", base, key, timeout=timeout)


if __name__ == "__main__":
    # ponytail: 不联网。llm.chat 是唯一的出网口，在模块边界换成假的，只验两件事——
    # 喂给它的参数对不对、回来的 JSON 解析得住。会坏的就是这两处。
    from unittest.mock import patch

    try:
        from . import llm as _llm
    except ImportError:
        import llm as _llm

    os.environ.pop(JEV_ENV, None)
    os.environ.pop(JEV_BASE_ENV, None)
    os.environ.pop("DEEPSEEK_API_KEY", None)

    state = {"chat": {"relationship": "friends", "latest_from": "her",
                      "messages": [{"from": "her", "text": "在吗"}]}}
    questions = {
        "literal_question": {"type": "noul", "instructions": "是字面意思吗？",
                             "criteria": {"true": "平铺直叙", "false": "有潜台词"}},
        "true_intent": {"type": "choice", "instructions": "真实意图？",
                        "criteria": {"casual_chat": "闲聊", "vent_anger": "生气"}},
        "danger_level": {"type": "score", "instructions": "离吵架多近？",
                         "criteria": ["没有", "有点"]},
    }
    seen: dict = {}

    def _fake_chat(protocol, base, key, model, system, turns, **kw):
        seen.update(protocol=protocol, base=base, key=key, model=model,
                    system=system, turns=turns, kw=kw)
        return json.dumps({"answers": {"literal_question": {"type": "noul", "noul": 0.9}}})

    with patch.object(_llm, "chat", _fake_chat):
        # 老名字迁移：起草那把还认 DEEPSEEK_API_KEY；判断那把不再退回 OPENROUTER_API_KEY
        os.environ["DEEPSEEK_API_KEY"] = "ds-legacy"
        assert _api_key(LLM_ENV) == "ds-legacy"
        try:
            _api_key(JEV_ENV)
            raise SystemExit("判断那把不该再有 OPENROUTER_API_KEY 这个退路")
        except JevError:
            pass
        os.environ[JEV_ENV] = "ds-key"

        # 默认来源 deepseek：协议、地址、模型、参数都得原样到位
        got = ask(state, questions)
        assert got == {"answers": {"literal_question": {"type": "noul", "noul": 0.9}},
                       "usage": {}}
        assert seen["protocol"] == "openai" and seen["base"] == "https://api.deepseek.com"
        assert seen["model"] == "deepseek-flash" and seen["key"] == "ds-key"
        assert seen["kw"]["response_format"] == {"type": "json_object"}
        assert seen["kw"]["extra_body"] == {"thinking": {"type": "disabled"}}
        assert seen["kw"]["temperature"] == 0.0 and seen["kw"]["max_tokens"] == JUDGE_MAX_TOKENS
        # 题面：三种题型的标签/档位都要原样带出去，答案才能按标签回来
        prompt = seen["turns"][0]
        for bit in ("literal_question", "true_intent", "danger_level", "casual_chat",
                    "vent_anger", "在吗", "是字面意思吗？", "friends", "对方"):
            assert bit in prompt, bit
        assert all(t in prompt for t in ('{"type":"noul"', '{"type":"choice"', '{"type":"score"'))

        # 显式传 model 盖过默认；来源表里没有的名字退回默认那条，不能炸
        ask(state, questions, model="deepseek-v4-pro")
        assert seen["model"] == "deepseek-v4-pro"
        assert ask(state, questions, provider="nope")["answers"]

        # JEV_BASE_URL 改地址（判断不出本机）：extra 不能再带，那是 DeepSeek 自家的字段
        os.environ[JEV_BASE_ENV] = "http://127.0.0.1:11434/v1"
        ask(state, questions)
        assert seen["base"] == "http://127.0.0.1:11434/v1" and seen["kw"]["extra_body"] is None
        os.environ.pop(JEV_BASE_ENV, None)

        # 「获取模型」打的是同一个地址，不能拿判断的 key 去打别家
        def _fake_list(protocol, base, key, **kw):
            seen.update(list_protocol=protocol, list_base=base, list_key=key)
            return ["deepseek-flash", "deepseek-v4-pro"]

        _llm.list_models = _fake_list
        assert list_models("deepseek", "ds-key") == ["deepseek-flash", "deepseek-v4-pro"]
        assert seen["list_base"] == "https://api.deepseek.com"
        assert seen["list_protocol"] == "openai" and seen["list_key"] == "ds-key"
        os.environ[JEV_BASE_ENV] = "http://127.0.0.1:11434/v1"
        list_models("deepseek", "ds-key")
        assert seen["list_base"] == "http://127.0.0.1:11434/v1"
        os.environ.pop(JEV_BASE_ENV, None)

        # 个别端点不认 response_format，会拿 ```json 包一层，得剥掉
        _llm.chat = lambda *a, **k: '```json\n{"answers": {"x": {"type": "noul", "noul": 0.4}}}\n```'
        assert ask(state, questions)["answers"]["x"]["noul"] == 0.4
        _llm.chat = lambda *a, **k: '```\n{"answers": {"y": {"type": "noul", "noul": 0.1}}}\n```'
        assert ask(state, questions)["answers"]["y"]["noul"] == 0.1
        # 回的不是 JSON / 顶层不是对象 / 没有 answers，都要是一句人话的 JevError
        for bad, want in (("我觉得她有点生气", "不是 JSON"), ('{"foo": 1}', "没有 answers"),
                          ("[1, 2]", "不是对象")):
            _llm.chat = lambda *a, _bad=bad, **k: _bad
            try:
                ask(state, questions)
                raise SystemExit(f"应当抛错：{bad!r}")
            except JevError as e:
                assert want in str(e), (bad, str(e))

    # 脱敏：老名字也得管，报错文本里不能漏出任何一把
    os.environ[JEV_ENV] = "ds-key"
    os.environ["DEEPSEEK_API_KEY"] = "ds-legacy"
    assert redact_secrets("key=ds-key ds-legacy") == "key=[REDACTED] [REDACTED]"

    # 取 key 的优先级：环境变量 > 设置文件（设置文件靠注入的回调拿）
    os.environ.pop(JEV_ENV, None)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    set_key_source(lambda name: "from-config")
    assert _api_key(JEV_ENV) == "from-config"
    os.environ[JEV_ENV] = "from-env"
    assert _api_key(JEV_ENV) == "from-env"          # 环境变量赢
    os.environ.pop(JEV_ENV, None)
    os.environ["DEEPSEEK_API_KEY"] = "from-legacy"
    assert _api_key(JEV_ENV) == "from-config"       # 判断那把没有老名字，老变量不该被它读到
    assert _api_key(LLM_ENV) == "from-legacy"       # 起草那把才有，老名字算环境变量那一档
    os.environ.pop("DEEPSEEK_API_KEY", None)
    set_key_source(lambda name: "")
    try:
        _api_key(JEV_ENV)                            # 两边都没有 → 报错，且要说清去哪填
        raise SystemExit("应当抛错")
    except JevError as e:
        assert "没配置" in str(e) and "设置页" in str(e)
    set_key_source(None)  # 还原，别影响别的调用方
    print("jev_client ok")
