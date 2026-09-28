# -*- coding: utf-8 -*-
"""设置持久化：所有设置（含两把 key）都落 config.json，就在 exe / 项目根旁边。

key 不写 Windows 环境变量、不碰注册表——环境变量是全用户可见的，别的程序能继承到，
还得广播 WM_SETTINGCHANGE 才生效。写在自己的设置文件里更简单也更好找。
**config.json 在 .gitignore 里**，不然 key 会被提交上去。

全程只有两把：判断 JEV_API_KEY、起草 LLM_API_KEY，跟选哪家来源无关。
core/ 不自己读配置——app 启动时把 key_of 注入 core.jev_client.set_key_source。"""
from __future__ import annotations

import json
import os
import re
import time
import sys  # 只为下面这一处：打包后 __file__ 指向临时解包目录，config.json 得放在 exe 旁边才存得住

from core.providers import CUSTOM, DRAFT_PROVIDERS, JEV_ENV, JEV_PROVIDERS, LLM_ENV

_ROOT = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
         else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CONFIG = os.path.join(_ROOT, "config.json")
# 新会话在用户还没单独设过之前用哪个关系。上游默认是「恋人」，
# 但对一个刚加进来的人先假定是恋人太奇怪了——朋友是最不冒犯的起点。
_DEFAULT_RELATIONSHIP = "friends"
_DEFAULT_CONTEXT = 10
_DEFAULT_JEV = "deepseek"  # 本 fork 不用 Jev；要回上游行为就改成 "openrouter"
_DEFAULT_DRAFT = "deepseek"


def _read(name: str, default=None):
    """读 config.json 里的一个字段；每次都重新读文件，改设置不用重启进程。"""
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            value = json.load(f).get(name)
    except (OSError, ValueError):
        return default
    return default if value is None else value

def _page_field(chat: str | None, key: str) -> str | None:
    """从那一页的画像里读 `**关系**：xxx` 这种行。没有这一页、或者没这一行，返回 None。

    界面和 wiki 页面共用同一份——用户给某个人设了关系，打开资料页就该看见，
    而不是一边存 config.json、一边页面上还写着「怎么认识的」这种提示语。"""
    path = _page(chat) if chat else ""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    found = re.search(rf"^\*\*{_FIELD_LABELS[key]}\*\*[:：][ \t]*(.*)$", text, flags=re.M)
    return found.group(1).strip() if found else None


def set_chat_profile(chat: str, relationship_text: str | None = None,
                     style_text: str | None = None) -> None:
    """把关系背景 / 说话风格写进那一页的画像。None = 这一项不动。

    没有那一页就先按模板建一个。写失败不抛——界面上改的东西没存上，
    下次打开会回到旧值，但不该因此崩。"""
    if not chat:
        return
    path = ensure_wiki_page(chat)
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return
    for key, value in (("relationship", relationship_text), ("style", style_text)):
        if value is None:
            continue
        label = _FIELD_LABELS[key]
        line = f"**{label}**：{value.strip()}"
        pattern = rf"^\*\*{label}\*\*[:：].*$"
        if re.search(pattern, text, flags=re.M):
            text = re.sub(pattern, line, text, count=1, flags=re.M)
        elif "## 画像" in text:  # 老页面没有这两行，补在画像标题下面
            text = text.replace("## 画像", f"## 画像\n\n{line}", 1)
        else:
            text = text.rstrip() + f"\n\n## 画像\n\n{line}\n"
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        pass


def relationship(chat: str | None = None) -> str:
    """关系背景。给了会话名就先看**这个人的**，没设过才回落到全局默认。

    关系本来就因人而异——同一个人对恋人和对同事说话不是一套。"""
    per = _page_field(chat, "relationship") if chat else None
    return str(per) if per else _DEFAULT_RELATIONSHIP


def chat_relationship_raw(chat: str) -> str:
    """只取「这个会话自己设的」关系，没设过返回空串——界面靠它决定下拉框停在哪。"""
    return str(_page_field(chat, "relationship") or "")

def context() -> int:
    """参考上下文条数：起草和判断各看最近多少条消息。3~30，缺失/脏数据一律退默认值。"""
    try:
        n = int(_read("context", _DEFAULT_CONTEXT))
    except (TypeError, ValueError):
        return _DEFAULT_CONTEXT
    return max(3, min(30, n))

def style(chat: str | None = None) -> str:
    """说话风格（可选，自由文本），只喂给起草模型。给了会话名就先看这个人的。

    默认空 = 只照着最近的消息模仿。空串是有效值（表示「这个人没单独设过」），
    所以这里用 `is None` 判断有没有设过，不能用真假值。"""
    per = _page_field(chat, "style") if chat else None
    return str(per) if per is not None else ""

def language() -> str:
    """配置中选择的界面语言；启动环境变量的覆盖由 i18n 处理。"""
    return str(_read("lang") or "zh").strip().lower()

def jev_provider() -> str:
    """判断模型走哪家：deepseek（默认）/ openrouter / typesafe 直连，见 core.providers.JEV_PROVIDERS。"""
    v = _read("jev_provider")
    return v if v in JEV_PROVIDERS else _DEFAULT_JEV

def jev_model() -> str:
    """判断模型 id；空 = 用该来源的默认模型。"""
    return str(_read("jev_model") or "") or JEV_PROVIDERS[jev_provider()].default

def draft_provider() -> str:
    """起草走哪家（见 core/providers.DRAFT_PROVIDERS）。老配置里的 openrouter/deepseek 照样认。"""
    v = _read("draft_provider")
    return v if v in DRAFT_PROVIDERS else _DEFAULT_DRAFT

def draft_provider_name() -> str:
    return DRAFT_PROVIDERS[draft_provider()].name

def draft_model() -> str:
    """起草模型 id；空 = 用该来源的默认模型（有的来源没有默认，那就得自己选）。"""
    return str(_read("draft_model") or "") or DRAFT_PROVIDERS[draft_provider()].default

def draft_base_url() -> str:
    """自定义来源的 Base URL；其余来源用表里的，这里返回空。"""
    return str(_read("draft_base_url") or "") if draft_provider() in CUSTOM else ""

def reply_target() -> bool:
    """群聊指定回复对象：开了才在界面上选回复给谁、才把对象喂给模型。默认关。"""
    return bool(_read("reply_target", False))

def thinking() -> bool:
    """起草时是否开思考模式：慢且贵，默认关。只有 DeepSeek / OpenRouter / Anthropic / Gemini 吃它。"""
    return bool(_read("thinking", False))

def debug_view() -> bool:
    """调试视图：另开一个窗口实时画识别框。默认关，开了子进程才往队列里送帧。"""
    return bool(_read("debug_view", False))

# 两把 key 存在 config.json 里。**不写 Windows 环境变量、不碰注册表**：
# 环境变量是全用户可见的，还得广播 WM_SETTINGCHANGE 才生效；写在自己的设置文件里，
# 用户找得到、删得掉，也不会把 key 泄漏给别的程序继承。config.json 在 .gitignore 里。
_KEY_FIELDS = {JEV_ENV: "jev_key", LLM_ENV: "llm_key"}


def key_of(env_name: str) -> str:
    """core/ 通过这个取 key——app 启动时注入 core.jev_client.set_key_source(settings.key_of)。"""
    return str(_read(_KEY_FIELDS[env_name]) or "")


def _get_key(env_name: str) -> str:
    """两把 key 之一。老版本按来源分开存的环境变量不再读，升级时重填一次即可。"""
    return key_of(env_name)

def jev_key() -> str:
    """判断那把 key，各家来源共用。"""
    return _get_key(JEV_ENV)

def has_jev_key() -> bool:
    return bool(jev_key())

def llm_key() -> str:
    """起草那把 key，所有语言模型来源共用。"""
    return _get_key(LLM_ENV)

def has_llm_key() -> bool:
    return bool(llm_key())

has_key = has_jev_key  # 旧名字：界面上「配没配好」问的就是判断模型这把 key


# —— 微信对话知识库（docs/wiki/，不进版本库）——
# 一个人一页，上半是画像、下半是记录。起草前把「画像」那一半喂进提示词，
# 回复就会越来越贴这个人。见 docs/wiki/README.md。

_WIKI_DIR = os.path.join(_ROOT, "docs", "wiki")
_WIKI_MAX = 1200          # 画像截断长度：太长会挤掉判断小抄和口吻样本
_WIKI_PICKS = 8           # 最近几条选择记录跟着一起喂
_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_CHOICE_HEAD = "## 选择记录"
# 画像里由程序写的那两行。用户设了关系/风格就写进页面，一个地方一份——
# 不再另存 config.json，否则页面上写着「怎么认识的」而界面里已经是「朋友」，两边对不上。
_FIELD_LABELS = {"relationship": "关系", "style": "说话风格"}


def wiki_dir() -> str:
    return _WIKI_DIR


def _page(chat_name: str) -> str:
    """会话名 → 那一页的路径。名字直接来自 OCR，可能带文件名非法字符，先洗一遍。"""
    name = _BAD_CHARS.sub("_", (chat_name or "").strip()).strip(" .")
    return os.path.join(_WIKI_DIR, name + ".md") if name else ""


def wiki_page_path(chat_name: str) -> str:
    """给界面用：这个会话的资料页在哪（不一定存在）。"""
    return _page(chat_name)


def _plain(text: str) -> str:
    """把一页的 markdown 压成能直接塞进提示词的几行：去标题、去注释、去空行。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)      # 模板里的说明注释
    keep = [ln.rstrip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith(("#", "|", "---"))]
    return re.sub(r"\n{2,}", "\n", "\n".join(keep)).strip()


def ensure_wiki_page(chat_name: str) -> str:
    """没有这一页就从 `_模板.md` 建一个（第一行的标题换成会话名）。返回路径，建不了给空串。

    **在要用它之前调**（分析开始那一下），不是微信列表里扫到名字就建：
    列表里还有订阅号、服务通知、群公告这些，扫到就建会攒一屏空页。
    真正算「有来有往的会话」的判据就是——对方发了新消息、程序决定要分析了。"""
    path = _page(chat_name)
    if not path:
        return ""
    if os.path.exists(path):
        return path
    name = os.path.basename(path)[:-3]
    try:
        with open(os.path.join(_WIKI_DIR, "_模板.md"), encoding="utf-8") as fh:
            body = fh.read()
    except OSError:  # 模板被删了也得能建，退到最小骨架
        body = "# 会话名\n\n## 画像\n\n## 记录\n\n## 选择记录\n"
    body = re.sub(r"^#[^\n]*", f"# {name}", body, count=1, flags=re.M)
    try:
        os.makedirs(_WIKI_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError:
        return ""
    return path


def wiki_note(chat_name: str) -> str:
    """读那一页，返回喂给起草的背景资料，没有就返回空串。

    两块：**画像**（`## 记录` 之前那半——这个人是谁、在意什么、雷区）+
    **最近几条选择记录**（我在三条候选里点过哪条——最直接的偏好信号）。
    中间那半「记录」不要：会一直往后长，又贵又跑题，大多是琐事。"""
    path = _page(chat_name)
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""  # 没这一页是常态，不是错误
    head = _plain(re.split(r"^#+\s*记录\s*$", text, maxsplit=1, flags=re.M)[0])
    picks = re.search(rf"^{re.escape(_CHOICE_HEAD)}\s*$", text, flags=re.M)
    if picks:
        rows = [ln.strip() for ln in text[picks.end():].splitlines()
                if ln.strip().startswith("-")]
        if rows:
            head += ("\n\n我以前在这个人面前点过这些回复（说明我的偏好，照这个感觉写）：\n"
                     + "\n".join(rows[-_WIKI_PICKS:]))
    return head[:_WIKI_MAX]


def record_choice(chat_name: str, candidates: list, index: int) -> None:
    """记下用户在三/两条候选里点了哪条。**只增不改**，追加到那页的「选择记录」下面。

    这是最直接的偏好信号——比「说话风格」那种自述准得多，因为是行为不是自评。
    写不进去（目录只读、名字非法之类）就算了：**绝不能因为这个让「填入」失败**。"""
    path = _page(chat_name)
    if not path or not (0 <= index < len(candidates)):
        return
    text = " ".join(str(candidates[index]).split())
    if not text:
        return
    try:
        os.makedirs(_WIKI_DIR, exist_ok=True)
        try:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            body = f"# {os.path.basename(path)[:-3]}\n\n## 画像\n\n"
        line = f"- [{time.strftime('%Y-%m-%d %H:%M')}] 第 {index + 1}/{len(candidates)} 条：{text}"
        if _CHOICE_HEAD in body:
            body = body.rstrip() + "\n" + line + "\n"
        else:
            body = body.rstrip() + f"\n\n{_CHOICE_HEAD}\n\n{line}\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError:
        pass

def save(context_n: int | None = None, *,
         jev_provider_text: str | None = None, jev_key_text: str | None = None,
         jev_model_text: str | None = None, draft_provider_text: str | None = None,
         llm_key_text: str | None = None, draft_model_text: str | None = None,
         draft_base_url_text: str | None = None, reply_target_on: bool | None = None,
         thinking_on: bool | None = None,
         debug_view_on: bool | None = None,
         lang_text: str | None = None) -> None:
    """每个参数为空/None = 保留当前值。两把 key 一并写进 config.json（那个文件不进版本库）。"""
    jev = jev_provider_text if jev_provider_text in JEV_PROVIDERS else jev_provider()
    draft = draft_provider_text if draft_provider_text in DRAFT_PROVIDERS else draft_provider()
    # key：None = 这次没碰那一栏，保持原样；有值就换掉。没有「清空 key」这个操作。
    keys = {_KEY_FIELDS[env]: typed.strip()
            for env, typed in ((JEV_ENV, jev_key_text), (LLM_ENV, llm_key_text)) if typed}
    n = context() if context_n is None else max(3, min(30, int(context_n)))
    # 空串 = 清掉，None = 原样留着（读原始字段，别读补过默认值的那个）
    keep = lambda new, name: str(_read(name) or "") if new is None else str(new).strip()
    flag = lambda new, now: now() if new is None else bool(new)
    # 整个 dict 必须在 open(..., "w") **之前**拼好：open 一上来就把文件截断，
    # 之后再 _read() 读到的是空文件，None 那几项就不是「保留」而是被清空了。
    data = {
        # 关系为空 = 只改别的开关（调试视图那种单项保存），别把它写没了
        "context": n,
        "jev_provider": jev, "jev_model": keep(jev_model_text, "jev_model"),
        "draft_provider": draft, "draft_model": keep(draft_model_text, "draft_model"),
        "draft_base_url": keep(draft_base_url_text, "draft_base_url"),
        "reply_target": flag(reply_target_on, reply_target),
        "thinking": flag(thinking_on, thinking),
        "debug_view": flag(debug_view_on, debug_view),
        **keys,  # 两把 key 也存这儿；config.json 在 .gitignore 里，不会被提交
    }
    lang = _read("lang") if lang_text is None else lang_text.strip().lower()
    if lang is not None:
        data["lang"] = lang
    with open(_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
