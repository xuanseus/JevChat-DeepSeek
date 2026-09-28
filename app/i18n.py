# -*- coding: utf-8 -*-
"""界面文案翻译。默认中文原样返回，设成别的语言才查表。

用法：界面文案包一层 `T("采集中")`，或者更常见的 `bind(控件, "采集中")` / `_tlabel("采集中")`
（这两个内部都会调 T）。表里没有的键**原样返回**，所以翻译可以慢慢补，漏一条也只是那一条
显示中文。语言来源：环境变量 `JEVCHAT_LANG`，或 config.json 的 `lang`。

改文案时的坑：**键是中文字符串本身**。代码里把哪个中文字改了一个字，这里对应的键就失效了，
那条会静默退回中文。改文案记得同步这张表。
"""
from __future__ import annotations

import os

from app import settings

LANGUAGES = [("简体中文", "zh"), ("English", "en")]

EN = {
    # 标题栏 / 采集开关
    "采集中": "Capturing",
    "已暂停": "Paused",
    "开启或暂停采集": "Start or pause capture",
    "设置": "Settings",
    "最小化": "Minimize",
    "关闭助手": "Close assistant",
    "关闭更新提示": "Dismiss update notice",
    "前往设置": "Open settings",
    "返回": "Back",
    "返回回复建议": "Back to suggestions",
    # 主面板
    "回复建议": "Suggestions",
    "推荐回复": "Suggested reply",
    "复制这条回复": "Copy this reply",
    "填入": "Fill in",
    "填入 {reply}": "Fill in {reply}",
    "当前会话": "Current chat",
    "跟随": "Following",
    "浏览中": "Browsing",
    "尚未识别到会话": "No chat detected yet",
    "聊天窗口切到哪个会话这里就跟到哪个；也可以自己选一个，只看它的记录和建议":
        "Follows whichever chat you switch to. You can also pick one yourself to read its history "
        "and past suggestions.",
    "回复对象": "Reply to",
    "三条候选都按这个人来写；不选就跟着最近说话的那位":
        "All three candidates are written for this person. Leave unset to follow whoever spoke last.",
    "填入时在开头加「@名字 」。只是普通文字，不会变成真正的 @":
        "Adds \"@Name \" at the start. Plain text only — it will not become a real mention.",
    "对话参考": "Conversation cues",
    "对话参考 · 回复给 {name}": "Conversation cues · replying to {name}",
    "正在浏览「{name}」，只看不填；切回这个会话才能用。":
        "Viewing \"{name}\" — read only. Switch back to this chat to use it.",
    "根据当前聊天片段推测，可能理解有偏差。紧张度为 0–9 的参考评分。":
        "Inferred from the visible messages only, so it can be off. Tension is a 0–9 reference score.",
    "等待对方的新消息": "Waiting for their next message",
    "保持聊天窗口打开。": "Keep the chat window open.",
    "收到新消息后，回复建议会出现在这里。":
        "Reply suggestions show up here once a new message arrives.",
    "保持聊天窗口打开。\n收到新消息后，回复建议会出现在这里。":
        "Keep the chat window open.\nReply suggestions show up here once a new message arrives.",
    "AI 建议仅供参考，按你的语气调整后再发送。":
        "AI suggestions are only a starting point — adjust them to your own voice before sending.",
    "对方最近说": "They just said",
    "暂未判断": "Not judged yet",
    "上次建议": "Last suggestion",
    # 聊天记录
    "聊天记录": "Chat log",
    "展开聊天记录": "Show chat log",
    "收起聊天记录": "Hide chat log",
    "展开或收起聊天记录": "Show or hide the chat log",
    "识别到的聊天内容会显示在这里": "Recognized messages show up here",
    # 资料页（docs/wiki 里这个人的那一页）
    "看 TA 的资料": "Their profile",
    "收起 TA 的资料": "Hide their profile",
    " · 还没有": " · none yet",
    "展开或收起这个人的资料页": "Show or hide this person's profile page",
    "还没有这个人的资料页": "No profile page for this person yet",
    # 设置 — 语言
    "界面语言 / Language": "Interface language / 界面语言",
    "选择后立即生效，并自动保存。": "Applies immediately and saves automatically.",
    "语言已切换并保存。": "Language switched and saved.",
    "语言保存失败，请检查配置文件是否可写后重试。":
        "Could not save the language. Check that the config file is writable, then try again.",
    "本次选择立即生效；下次启动仍优先使用 JEVCHAT_LANG 指定的语言。":
        "Applies right away. Next launch will still prefer the language set by JEVCHAT_LANG.",
    # 设置 — 关系 / 口吻
    "关系": "Relationship",
    "你们的关系": "Your relationship",
    "例如：刚认识的朋友，正在慢慢熟悉":
        "e.g. a friend you just met, still getting to know each other",
    "自定义关系背景": "Describe the relationship yourself",
    "说话风格（可选）": "Speaking style (optional)",
    "例如：话少、不用标点、偶尔用 doge、不说客套话":
        "e.g. few words, no punctuation, occasional doge, no pleasantries",
    "说话风格": "Speaking style",
    "参考上下文": "Context messages",
    "参考的最近消息条数": "How many recent messages to include",
    "开": "On",
    "关": "Off",
    "群聊指定回复对象": "Pick who to reply to in group chats",
    "启动时检查更新": "Check for updates on launch",
    "调试视图": "Debug view",
    "回复偏好": "Reply preferences",
    "帮助助手把握称呼、语气和回应分寸。":
        "Helps calibrate how to address them, the tone, and how far to go.",
    "候选本来就照着你最近发的消息模仿；这里可以再补一句你自己的口吻。":
        "Candidates already imitate your recent messages. Add one line here to describe your own voice.",
    "生成和判断时看最近这么多条消息。太少会丢上下文，太多会稀释重点，建议 6–12。":
        "How many recent messages both drafting and judging get to see. Too few loses context, "
        "too many dilutes it. 6–12 works well.",
    "开了以后群聊里可以选回复给谁，候选会针对 TA 写，填入时可带 @。关了就正常回复。":
        "When on, you can choose who to reply to in a group chat and candidates are written for "
        "them. Off means a normal reply.",
    "只向 GitHub 查最新版本号，不发送任何数据。国内访问 GitHub 慢的话关掉也行。":
        "Only asks GitHub for the latest version number and sends no data.",
    "另开一个窗口实时显示截到的画面和识别框：绿 = 我、蓝 = 对方、灰 = 过滤掉的灰字、红 = 当成图片丢掉、黄 = 小字丢掉。只在内存里画，不存图。":
        "Opens a second window showing the captured frame and every recognized box: green = me, "
        "blue = them, grey = filtered-out grey text, red = dropped as an image, yellow = dropped "
        "as small text. Drawn in memory only, never saved.",
    # 设置 — 模型
    "判断": "Judge",
    "起草": "Draft",
    "判断 · Jev": "Judge · Jev",
    "判断 · 模型": "Judge · Model",
    "起草 · 语言模型": "Draft · Language model",
    "起草时开启思考模式": "Thinking mode while drafting",
    "保存设置": "Save settings",
    "来源": "Provider",
    "密钥": "API key",
    "模型": "Model",
    "获取模型": "Fetch models",
    "获取中…": "Fetching…",
    "已配置": "Configured",
    "未配置": "Not configured",
    "已配置，留空保留": "Already set — leave blank to keep",
    "输入 {name} API 密钥": "Enter your {name} API key",
    "共 {count} 个": "{count} total",
    "请先填写 {name} 的 API 密钥。": "Enter the {name} API key first.",
    "{name} 请先获取并选择一个模型。": "Fetch and pick a model for {name} first.",
    "获取失败，检查密钥、网络或 Base URL":
        "Fetch failed — check the API key, your network, or the Base URL",
    "这个来源没返回任何模型": "This provider returned no models",
    "设置已保存，将用于下一次回复。": "Settings saved. They apply from the next reply on.",
    "判断意图、紧张度，并给三条候选排序。两家给的是同一个 Jev，必填。":
        "Judges intent and tension, then ranks the three candidates. Required.",
    "写那三条候选。OpenAI / Anthropic / Gemini 三种接口都走各自官方 SDK。默认 DeepSeek 官网直连，国内最快。":
        "Writes the three candidates. OpenAI / Anthropic / Gemini each go through their own "
        "official SDK. DeepSeek direct is the default and fastest from mainland China.",
    "保存后用于下一次生成的回复。": "Applies to the next generated reply after saving.",
    "OpenRouter 的 key 或 TypeSafe 的 key，看上面选的来源。":
        "Use the key matching the provider you picked above.",
    "上面选哪家就填哪家的 key；换来源重填一次，只存这一把。":
        "Enter the key for the provider chosen above. Switching providers means re-entering it; "
        "only one key is stored per slot.",
    "关：秒回，够用。开：模型先想再写，更斟酌但慢好几倍、贵一些。只有 {providers} 认这个开关。":
        "Off: instant and usually good enough. On: the model thinks before writing — more "
        "considered, but several times slower and pricier. Only {providers} honor this switch.",
    "https://你的服务/v1": "https://your-service/v1",
    "自定义来源 Base URL": "Custom provider Base URL",
    "先填密钥": "Enter the API key first",
    "先填 Base URL": "Enter the Base URL first",
    "请填写关系背景，或选择一个已有选项。":
        "Describe the relationship, or pick one of the presets.",
    "自定义来源要填 Base URL。": "A custom provider needs a Base URL.",
    "先设置，再开始": "Set up first",
    "配置模型和关系背景，": "Configure a model and your relationship,",
    "让建议更贴近你们的对话。": "and suggestions will fit your conversation better.",
    "配置模型和关系背景，\n让建议更贴近你们的对话。":
        "Configure a model and your relationship,\nand suggestions will fit your conversation better.",
    "调整关系背景，配置判断和起草用的两个模型。":
        "Adjust the relationship and set up the two models — one for judging, one for drafting.",
    # 状态消息
    "设置已就绪，等待新消息": "Ready — waiting for a new message",
    "采集已暂停": "Capture paused",
    "采集已暂停，聊天内容不再读取": "Capture paused; messages are no longer read",
    "聊天内容暂时不再读取。": "Messages are no longer being read.",
    "打开标题栏的开关，继续接收新消息。":
        "Flip the switch in the title bar to start reading again.",
    "聊天内容暂时不再读取。\n打开标题栏的开关，继续接收新消息。":
        "Messages are no longer being read.\nFlip the switch in the title bar to start again.",
    "正在根据新消息整理回复…": "Working out a reply for the new message…",
    "暂时没有可用的回复": "No usable reply right now",
    "请按上方提示处理。收到新的对方消息后会再次尝试。":
        "Follow the prompt above. It will retry when their next message arrives.",
    "建议已更新，选一句适合你的回复": "Updated — pick the reply that fits you",
    "未生成可用回复，请等待下一条新消息。":
        "No usable reply was produced. Wait for the next new message.",
    "保存失败，请检查配置文件是否可写后重试。":
        "Save failed. Check that the config file is writable, then try again.",
    "未能填入，请确认聊天窗口可用后重试，或复制回复。":
        "Could not fill it in. Make sure the chat window is usable, or copy the reply instead.",
    "已尝试填入，请确认内容后发送。": "Filled in — check it, then send it yourself.",
    "回复已复制，可粘贴并修改。": "Reply copied — paste it and edit as you like.",
    "等待新消息": "Waiting for a new message",
    "请先在设置中配置模型": "Configure a model in settings first",
    "正在想一句合适的回复": "Thinking of a good reply",
    "正在结合上下文生成建议，稍等一下。":
        "Generating suggestions from the conversation — one moment.",
    "你已回复，等待对方的新消息": "You replied — waiting for their next message",
    "未找到聊天窗口，打开后再开启采集":
        "No chat window found. Open it, then turn capture on.",
    "生成失败，请检查网络和服务设置；新消息到来后会重试。":
        "Generation failed. Check your network and provider settings; it retries on the next message.",
    # 调试窗口
    "识别调试": "Recognition debug",
    "等待画面…": "Waiting for a frame…",
    "开着采集，聊天窗口有动静就会有帧":
        "With capture on, frames arrive whenever the chat window changes",
    "认不出消息区": "Could not locate the message area",
    "最近一帧 —— · 等待中…": "Latest frame —— · waiting…",
    "最近一帧 {stamp} · 共 {count} 个框": "Latest frame {stamp} · {count} boxes",
    "会话：{title}": "Chat: {title}",
    "（未识别）": "(not recognized)",
    "消息区：{area}": "Message area: {area}",
    "头部顶：y {top}": "Header top: y {top}",
    "OCR 耗时：{elapsed} ms": "OCR took {elapsed} ms",
    "帧：{width}×{height}（原帧缩了 1/{scale} 再过队列）":
        "Frame: {width}×{height} (original scaled 1/{scale} before queueing)",
    "框：{counts}": "Boxes: {counts}",
    "无": "none",
    "本帧 {count} 行": "{count} lines this frame",
    "图例（蓝粗框 = 消息区，紫细框 = 头部会话名）":
        "Legend (thick blue box = message area, thin purple box = chat name in header)",
    "绿": "green",
    "蓝": "blue",
    "灰": "grey",
    "橙": "orange",
    "红": "red",
    "黄": "yellow",
    "过滤掉的灰字": "filtered-out grey text",
    "当成发言人名": "taken as a speaker name",
    "当成图片丢掉": "dropped as an image",
    "小字丢掉": "dropped as small text",
    "去下载": "Download",
    # 关系预设
    "恋人": "Romantic partners",
    "朋友": "Friends",
    "同事": "Colleagues",
    "家人": "Family",
    "自定义": "Custom",
    # 判断标签（core/questions.py 的 CHOICE_LABELS）
    "希望确认你在意": "Wants reassurance you care",
    "表达不满或受伤": "Venting anger or hurt",
    "希望你采取行动": "Wants you to act",
    "希望了解原因": "Wants an explanation",
    "轻松交流": "Casual chat",
    "平和结束话题": "Closing the topic peacefully",
    "先核对聊天记录": "Check the chat history first",
    "为已知问题道歉": "Apologize for a known fault",
    "给出具体承诺": "Make a concrete commitment",
    "说明事实与原因": "Explain the facts and why",
    "回应并表达理解": "Acknowledge and show you get it",
    "简短回应或留白": "Keep it short or say nothing",
    "商量具体安排": "Work out the logistics",
    "真诚道歉": "A sincere apology",
    "具体行动或安排": "A concrete action or plan",
    "清楚的解释": "A clear explanation",
    "关注与在意": "Attention and care",
    "可能无需补充回应": "Probably needs nothing more",
    # 界面各处
    "备选": "Alternative",
    "填入时带 @": "Add @ when filling in",
    "展开": "Show",
    "收起": "Hide",
    "我": "Me",
    "对方": "Them",
    "建议：": "Suggested: ",
    "可能意图 · ": "Likely intent · ",
    "可能需要 · ": "Probably needs · ",
    "紧张度": "Tension",
    "紧张度待判断": "Tension not judged yet",
    "需要配置模型": "Model setup needed",
    "仅填入输入框 · 发送由你确认": "Fills the input box only · you press send",
    "有新版本 v": "New version v",
    "有新版本 v{version}": "New version v{version}",
    "更新": "updated",
    "按「{name}」重新生成…": "Regenerating for \"{name}\"…",
    "未找到聊天窗口，请确认已经打开":
        "No chat window found — make sure it is open",
    "输入区域尚不可用，请确认聊天窗口可见（不要最小化）":
        "The input area is not available. Make sure the chat window is visible (not minimized).",
    "分析失败: ": "Analysis failed: ",
    # 这两条是拼句片段，在 main.py 里跟来源名拼起来用。**是单引号写的**
    # （`T('起草来源 ')`），所以按双引号搜「有没有人用」会漏掉——我就是这么误删过一次。
    "起草来源 ": "Draft provider ",
    " 没填密钥，去设置里补上": " has no API key — add it in settings",
}

TABLES = {"en": EN}


def _lang() -> str:
    env = (os.environ.get("JEVCHAT_LANG") or "").strip().lower()
    if env:
        return env
    try:
        return settings.language()
    except Exception:
        return "zh"


_LANG = _lang()
_TABLE = TABLES.get(_LANG, {})


def T(text: str) -> str:
    """界面文案：查得到就翻译，查不到原样返回。"""
    return _TABLE.get(text, text)


def language() -> str:
    """当前进程正在显示的语言，可能由设置页临时覆盖启动环境。"""
    return _LANG


def reload(lang: str | None = None) -> None:
    """显式选择立即覆盖当前语言；省略参数则重新读取启动配置。"""
    global _LANG, _TABLE
    _LANG = _lang() if lang is None else (lang.strip().lower() or "zh")
    _TABLE = TABLES.get(_LANG, {})


def bind(widget, source, setter="setText"):
    """保留中文 key 或动态文案函数，在语言变化时重放指定的 setter。"""
    bindings = getattr(widget, "_i18n_bindings", None)
    if bindings is None:
        bindings = widget._i18n_bindings = {}
    bindings[setter] = source
    getattr(widget, setter)(source() if callable(source) else T(source))
    return widget


def retranslate(root) -> None:
    """只刷新显式绑定的界面文案，避免把聊天内容或用户输入当成翻译键。"""
    from PySide6.QtCore import QObject

    for widget in [root, *root.findChildren(QObject)]:
        for setter, source in getattr(widget, "_i18n_bindings", {}).items():
            getattr(widget, setter)(source() if callable(source) else T(source))


if __name__ == "__main__":  # 自测
    # 中文原样返回；表里没有的键也原样返回（漏翻只是那一条显示中文，不该炸）
    _TABLE = {}
    assert T("采集中") == "采集中" and T("没有这条") == "没有这条"
    _TABLE = EN
    assert T("采集中") == "Capturing" and T("没有这条") == "没有这条"
    # 空译文等于没翻，还容易把界面弄成一片空白——直接拦下
    empty = [k for k, v in EN.items() if not v.strip()]
    assert not empty, empty
    # 占位符要跟原文对得上，少一个 format 时会 KeyError，多一个会留下没替换的 {x}
    import re as _re
    bad = []
    for k, v in EN.items():
        if sorted(_re.findall(r"\{(\w+)\}", k)) != sorted(_re.findall(r"\{(\w+)\}", v)):
            bad.append(k)
    assert not bad, f"占位符对不上：{bad}"

    # 源码里用到的中文文案，英文表里都得有——不然那条会静默显示中文。
    # 扫描三种把中文当键传进去的写法：T(...)、bind(控件, ...)、_tlabel(...)。
    #
    # 这个检查是被现实打出来的：之前我用「grep 双引号」判断哪些键没人用，
    # 结果 main.py 里 `T('起草来源 ')` 是**单引号**，漏了，把还在用的键删了。
    # 手写 grep 靠不住，落成自测才不会再犯。
    import glob
    import os as _os
    pattern = _re.compile(r"""(?:^|[^\w])(?:T|_tlabel)\(\s*["']([^"'\n]+)["']"""
                          r"""|bind\([^,]+,\s*["']([^"'\n]+)["']""")
    used = set()
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for path in glob.glob(_os.path.join(root, "app", "*.py")) + \
            glob.glob(_os.path.join(root, "core", "*.py")) + [_os.path.join(root, "main.py")]:
        if path.endswith("i18n.py"):
            continue
        for found in pattern.finditer(open(path, encoding="utf-8").read()):
            text = found.group(1) or found.group(2)
            if _re.search(r"[一-鿿]", text):
                # 源码里写的是 "\n" 两个字符，表里的键是真换行，得还原。
                # 别用 codecs/unicode_escape 那套——它会把中文的 UTF-8 字节当转义解，直接糊成乱码。
                used.add(text.replace("\\n", "\n").replace("\\t", "\t"))
    missing = sorted(used - set(EN))
    assert not missing, f"这些文案没有英文翻译：{missing}"
    print(f"i18n ok · en {len(EN)} strings · 源码引用 {len(used)} 条全部有译文")
