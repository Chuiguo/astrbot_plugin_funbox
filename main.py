from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime
import hashlib
import random
import re
import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


COMMAND_WORDS = {
    "趣味帮助",
    "趣味菜单",
    "菜单",
    "玩法",
    "funbox",
    "玩点啥",
    "来点好玩的",
    "推荐玩法",
    "随机玩法",
    "抽玩法",
    "funbox状态",
    "趣味状态",
    "盒子状态",
    "funbox清缓存",
    "趣味清缓存",
    "盒子清缓存",
    "funbox忘记我",
    "趣味忘记我",
    "盒子忘记我",
    "群聊榜单",
    "抽象王",
    "梗王",
    "问号王",
    "今日人设",
    "人设",
    "今日人格",
    "赛博塔罗",
    "塔罗",
    "抽卡",
    "氛围雷达",
    "气氛雷达",
    "群聊雷达",
    "名场面",
    "今日名场面",
    "今日运势",
    "运势",
    "抽象指数",
    "发疯指数",
    "抽象评分",
    "群聊热词",
    "热词",
    "群友小档案",
    "小档案",
    "群友档案",
    "群聊日报",
    "今日日报",
    "今日群聊日报",
    "空间侦探",
    "说说锐评",
    "空间锐评",
}

NATURAL_NAMES = ("funbox", "盒子", "小盒", "小盒子", "趣味盒")

MENU_CATEGORIES = {
    "常用": (
        ("氛围雷达", "看最近群聊气氛。"),
        ("名场面", "捞一句最近最有节目效果的话。"),
        ("今日人设", "生成 bot 今日轻人设。"),
        ("赛博塔罗", "抽一张赛博运势卡。"),
    ),
    "个人": (
        ("群友小档案", "根据最近发言生成轻量聊天画像。"),
        ("今日运势", "抽今天的轻量运势。"),
        ("抽象指数", "测一句话或本人近期发言的抽象程度。"),
    ),
    "群聊": (
        ("群聊热词", "统计最近反复出现的关键词。"),
        ("群聊日报", "总结最近热词、名场面和气质。"),
        ("群聊榜单", "抽象王、梗王、问号王轻量排行。"),
        ("氛围雷达", "用读数吐槽群聊空气。"),
    ),
    "空间": (
        ("空间侦探", "分析说说/空间动态，安全锐评。"),
    ),
    "不知道玩啥": (
        ("玩点啥", "按上下文推荐一个玩法。"),
        ("随机玩法", "随机抽一个玩法并给示例。"),
    ),
    "维护": (
        ("funbox状态", "查看当前会话缓存和配置状态。"),
        ("funbox清缓存", "清掉当前群聊 FunBox 内存样本。"),
        ("funbox忘记我", "删除当前用户在 FunBox 里的最近样本。"),
    ),
}

PLAY_EXAMPLES = (
    ("氛围雷达", "/氛围雷达", "最近聊天有点空气流动，适合扫一下气氛。"),
    ("名场面", "/名场面", "群里有梗味时用它，能捞节目效果。"),
    ("今日人设", "/今日人设", "想让 bot 先定个今日人格就用它。"),
    ("赛博塔罗", "/赛博塔罗", "样本不够或想来点玄学时很好用。"),
    ("群友小档案", "/群友小档案", "想看自己最近聊天画像时用它。"),
    ("今日运势", "/今日运势", "适合每天先整点轻量玄学。"),
    ("抽象指数", "/抽象指数 我是不是有点离谱", "适合给一句话测抽象读数。"),
    ("群聊热词", "/群聊热词", "最近大家反复念叨同一件事时用它。"),
    ("群聊日报", "/群聊日报", "群里聊了一阵后，用它收个尾。"),
    ("群聊榜单", "/群聊榜单", "样本多了以后可以看看今天谁最有节目效果。"),
    ("空间侦探", "/空间侦探 今天又被生活创飞了", "想锐评说说/空间文案时用它。"),
)


@register(
    "astrbot_plugin_funbox",
    "chuiguo+codex",
    "安全轻量的群聊趣味工具箱：人格化自然回复、玩法导航、群聊榜单、隐私控制",
    "0.9.0",
    "https://github.com/Chuiguo/astrbot_plugin_funbox",
)
class FunBoxPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self.max_cache_messages = self._config_int("max_cache_messages", 90, minimum=20)
        self.enable_natural_reply = self._config_bool("enable_natural_reply", True)
        self.only_when_addressed = self._config_bool("only_when_addressed", True)
        self.enable_llm = self._config_bool("enable_llm", True)
        self.persona_style = str(
            self._config_get(
                "persona_style",
                "跟随 AstrBot 当前人格，嘴有点损但不攻击，像熟人群友一样会接梗。",
            )
            or ""
        ).strip()
        self.natural_cooldown_seconds = self._config_int(
            "natural_cooldown_seconds",
            180,
            minimum=0,
        )
        self.enable_profiles = self._config_bool("enable_profiles", True)
        self.enable_auto_daily = self._config_bool("enable_auto_daily", False)
        self.daily_report_hour = min(
            23,
            max(0, self._config_int("daily_report_hour", 23, minimum=0)),
        )
        self.recent = defaultdict(lambda: deque(maxlen=self.max_cache_messages))
        self.profiles = defaultdict(dict)
        self.natural_last_reply_at = defaultdict(float)
        self.daily_report_sent = {}
        self.bot_names = set(NATURAL_NAMES)
        self._bot_login_checked = False
        for name in self._config_list("extra_trigger_names", []):
            self._add_bot_name(name)
        self._load_context_bot_names()
        logger.info("FunBoxPlugin loaded")

    def _config_get(self, key: str, default=None):
        try:
            if hasattr(self.config, "get"):
                return self.config.get(key, default)
        except Exception:
            return default
        return default

    def _config_bool(self, key: str, default: bool) -> bool:
        value = self._config_get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "开启"}
        return bool(value)

    def _config_int(self, key: str, default: int, *, minimum: int = 1) -> int:
        try:
            value = int(self._config_get(key, default))
        except Exception:
            value = default
        return max(value, minimum)

    def _config_list(self, key: str, default: list[str]) -> list[str]:
        value = self._config_get(key, default)
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return list(default)

    def _normalize_bot_name(self, name: object) -> str:
        return re.sub(r"\s+", "", str(name or "")).strip().lower()

    def _add_bot_name(self, name: object) -> None:
        normalized = self._normalize_bot_name(name)
        if len(normalized) >= 2:
            self.bot_names.add(normalized)

    def _load_context_bot_names(self) -> None:
        try:
            cfg = self.context.get_config()
        except Exception:
            return
        if not isinstance(cfg, dict):
            return
        for key in ("bot_name", "bot_names", "nickname", "name"):
            value = cfg.get(key)
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    self._add_bot_name(item)
            else:
                self._add_bot_name(value)

    async def _ensure_bot_names(self, event: AstrMessageEvent) -> None:
        if self._bot_login_checked:
            return
        bot = getattr(event, "bot", None)
        if bot is None:
            return

        self._bot_login_checked = True
        try:
            if hasattr(bot, "get_login_info"):
                info = await bot.get_login_info()
            else:
                info = await bot.api.call_action("get_login_info")
        except Exception as e:
            logger.debug(f"FunBox 获取 bot 昵称失败: {e}")
            return

        if isinstance(info, dict):
            self._add_bot_name(info.get("nickname"))
            self._add_bot_name(info.get("name"))

    def _session_key(self, event: AstrMessageEvent) -> str:
        return str(getattr(event, "unified_msg_origin", "") or "default")

    def _sender_name(self, event: AstrMessageEvent) -> str:
        try:
            return event.get_sender_name() or event.get_sender_id()
        except Exception:
            return "某位群友"

    def _sender_id(self, event: AstrMessageEvent) -> str:
        try:
            return str(event.get_sender_id())
        except Exception:
            return "unknown"

    def _message_text(self, event: AstrMessageEvent) -> str:
        text = getattr(event, "message_str", "") or ""
        if text:
            return text
        try:
            return getattr(event.message_obj, "message_str", "") or ""
        except Exception:
            return ""

    def _is_self_message(self, event: AstrMessageEvent) -> bool:
        try:
            sender_id = str(event.get_sender_id())
            self_id = str(getattr(event.message_obj, "self_id", ""))
            return bool(self_id and sender_id == self_id)
        except Exception:
            return False

    def _clean(self, text: str, limit: int = 90) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > limit:
            text = text[:limit] + "..."
        return text

    def _command_arg(self, event: AstrMessageEvent) -> str:
        text = self._message_text(event).strip()
        if not text:
            return ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    def _rng(self, event: AstrMessageEvent, salt: str) -> random.Random:
        day = datetime.now().strftime("%Y-%m-%d")
        raw = f"{day}|{self._sender_id(event)}|{salt}"
        seed = int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)
        return random.Random(seed)

    def _recent_context(self, event: AstrMessageEvent, limit: int = 35) -> str:
        items = list(self.recent[self._session_key(event)])[-limit:]
        lines = [
            f"{item['time']} {item['sender']}：{item['text']}"
            for item in items
            if item.get("text")
        ]
        return "\n".join(lines)

    def _get_provider(self, event: AstrMessageEvent):
        umo = getattr(event, "unified_msg_origin", None)
        try:
            if umo:
                return self.context.get_using_provider(str(umo))
            return self.context.get_using_provider()
        except Exception as e:
            logger.debug(f"FunBox 获取 LLM provider 失败: {e}")
            return None

    def _get_event_platform_name(self, event: AstrMessageEvent) -> str:
        getter = getattr(event, "get_platform_name", None)
        if callable(getter):
            try:
                platform_name = getter()
            except Exception:
                platform_name = None
            if platform_name:
                return str(platform_name)

        umo = getattr(event, "unified_msg_origin", None)
        if umo and ":" in str(umo):
            return str(umo).split(":", 1)[0]
        return ""

    def _get_provider_settings(self, event: AstrMessageEvent) -> dict:
        umo = getattr(event, "unified_msg_origin", None)
        try:
            cfg = self.context.get_config(str(umo)) if umo else self.context.get_config()
        except TypeError:
            try:
                cfg = self.context.get_config()
            except Exception:
                return {}
        except Exception:
            return {}

        if not isinstance(cfg, dict):
            return {}
        provider_settings = cfg.get("provider_settings", {})
        return provider_settings if isinstance(provider_settings, dict) else {}

    async def _current_persona_prompt(self, event: AstrMessageEvent) -> str:
        umo = getattr(event, "unified_msg_origin", None)
        if not umo:
            return ""

        persona_manager = getattr(self.context, "persona_manager", None)
        if persona_manager is None:
            return ""

        try:
            conversation_persona_id = None
            conversation_manager = getattr(self.context, "conversation_manager", None)
            if conversation_manager is not None:
                cid = await conversation_manager.get_curr_conversation_id(str(umo))
                if cid:
                    conversation = await conversation_manager.get_conversation(str(umo), cid)
                    if conversation:
                        conversation_persona_id = getattr(conversation, "persona_id", None)

            persona_id, persona, _, _ = await persona_manager.resolve_selected_persona(
                umo=str(umo),
                conversation_persona_id=conversation_persona_id,
                platform_name=self._get_event_platform_name(event),
                provider_settings=self._get_provider_settings(event),
            )
            if not persona and persona_id and hasattr(persona_manager, "get_persona_v3_by_id"):
                persona = persona_manager.get_persona_v3_by_id(persona_id)
            if isinstance(persona, dict):
                return str(persona.get("prompt") or "").strip()
        except Exception as e:
            logger.debug(f"FunBox 解析当前会话人格失败，使用插件人格配置: {e}")
        return ""

    def _clip_reply(self, text: str, limit: int = 520) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > limit:
            text = text[:limit].rstrip() + "..."
        return text

    async def _generate_with_context(
        self,
        event: AstrMessageEvent,
        *,
        task: str,
        fallback: str,
        limit: int = 520,
    ) -> str:
        if not self.enable_llm:
            return fallback
        provider = self._get_provider(event)
        if not provider:
            return fallback

        context_text = self._recent_context(event)
        persona_style = self.persona_style or "跟随 AstrBot 当前人格，短、聪明、会接梗。"
        astrbot_persona = await self._current_persona_prompt(event)
        persona_instruction = (
            f"AstrBot 当前会话人格：\n{astrbot_persona[:1200]}\n"
            if astrbot_persona
            else "AstrBot 当前会话人格：未读取到，使用 FunBox 人格/口吻配置。\n"
        )
        system_prompt = (
            "你是 FunBox，一个安全、轻量、嘴有点损但不攻击人的群聊趣味插件。\n"
            "你要基于最近群聊上下文生成中文短回复。不要泄露隐私，不做人身攻击，"
            "不要挑起争吵，不要输出黄赌毒或仇恨内容。\n"
            "风格：好笑、聪明、短、像群友能接上的梗。\n"
            f"当前 FunBox 人格/口吻：{persona_style}\n"
            f"{persona_instruction}"
            "如果 AstrBot 当前会话已经设置了人格或角色，请优先贴合当前人格，"
            "不要突然切换成完全陌生的人设。"
        )
        prompt = (
            f"最近群聊上下文：\n{context_text or '暂无，按当前用户和指令轻量发挥。'}\n\n"
            f"任务：\n{task}\n\n"
            "输出要求：\n"
            "- 直接输出最终回复，不要解释你在做什么。\n"
            "- 控制在 2~6 行。\n"
            "- 可以轻微抽象，但不要骂人、不要贴标签羞辱具体群友。"
        )
        try:
            response = await provider.text_chat(
                system_prompt=system_prompt,
                prompt=prompt,
            )
            text = getattr(response, "completion_text", "") or str(response)
            text = self._clip_reply(text, limit=limit)
            return text or fallback
        except Exception as e:
            logger.warning(f"FunBox LLM 生成失败，使用兜底模板: {e}")
            return fallback

    def _is_command_like(self, text: str) -> bool:
        if not text:
            return True
        if text.startswith(("/", "!", "！", ".", "。", "#")):
            return True
        first = text.split(maxsplit=1)[0]
        return first in COMMAND_WORDS

    def _is_addressed(self, text: str) -> bool:
        normalized = self._normalize_bot_name(text)
        return any(name and name in normalized for name in self.bot_names)

    def _detect_intent(self, text: str) -> str | None:
        lowered = text.lower()
        checks = (
            ("status", ("funbox状态", "趣味状态", "盒子状态", "状态怎么样", "缓存多少")),
            ("clear_cache", ("funbox清缓存", "趣味清缓存", "盒子清缓存", "清缓存", "清掉缓存", "清空样本")),
            ("forget_me", ("funbox忘记我", "趣味忘记我", "盒子忘记我", "忘记我", "删掉我的样本")),
            ("leaderboard", ("群聊榜单", "排行榜", "抽象王", "梗王", "问号王", "今日榜单")),
            ("recommend", ("来点好玩的", "玩点啥", "帮我选", "推荐玩法", "推荐一个", "现在玩啥")),
            ("random_play", ("随机玩法", "抽玩法", "随机一个", "随便来一个", "交给命运")),
            ("menu", ("菜单", "玩法列表", "有哪些玩法", "功能列表")),
            ("help", ("帮助", "怎么用", "你会什么", "funbox")),
            ("profile", ("小档案", "群友档案", "群友画像", "我的档案", "给我建档")),
            ("daily_report", ("日报", "今日总结", "今天群里", "群聊总结")),
            ("qzone", ("空间侦探", "说说锐评", "空间锐评", "空间报告", "分析说说", "锐评说说")),
            ("hot_words", ("热词", "关键词", "聊什么", "高频词")),
            ("scene", ("名场面", "经典发言", "哪句最", "节目效果")),
            ("vibe", ("氛围", "气氛", "群里咋样", "群聊咋样", "雷达")),
            ("tarot", ("塔罗", "抽卡", "占卜", "抽一张")),
            ("fortune", ("运势", "运气", "今日运", "今天怎么样")),
            ("persona", ("人设", "人格", "你今天", "今日人设")),
            ("abstract", ("抽象", "发疯", "疯癫", "我正常吗", "我有多")),
        )
        for intent, keywords in checks:
            if any(keyword in lowered for keyword in keywords):
                return intent
        return None

    def _looks_like_fun_request(self, text: str, intent: str | None) -> bool:
        if not intent:
            return False
        return any(
            marker in text
            for marker in (
                "吗",
                "嘛",
                "咋",
                "怎么",
                "什么",
                "看看",
                "帮",
                "来",
                "抽",
                "算",
                "测",
                "分析",
                "今天",
                "最近",
                "刚刚",
                "群里",
                "有没有",
                "给我",
            )
        )

    def _natural_fallback(self, intent: str | None) -> str:
        fallback_map = {
            "help": (
                "FunBox 可用玩法：今日人设、赛博塔罗、氛围雷达、名场面、"
                "今日运势、抽象指数、群聊热词。你也可以直接叫我的昵称，例如：群里现在啥氛围？"
            ),
            "status": "FunBox 状态可以用 /funbox状态 查看。",
            "clear_cache": "要清当前会话缓存，请发送 /funbox清缓存。",
            "forget_me": "要删除你的最近样本，请发送 /funbox忘记我。",
            "leaderboard": "群聊榜单还没有样本。先让群友聊几句，我再开始颁奖。",
            "menu": self._menu_text(),
            "recommend": "我建议现在玩：/赛博塔罗\n原因：样本还少，先抽一张赛博玄学不冷场。",
            "random_play": "随机玩法：/氛围雷达\n直接发它，我来一本正经地扫一下群聊空气。",
            "hot_words": "我还没攒够上下文，等群里再聊几句我就能抓热词。",
            "scene": "名场面仓库还没攒起来，先让群友发点能入史的。",
            "vibe": "氛围雷达正在预热。再聊几句，我就能开始一本正经地胡说八道。",
            "tarot": "你抽到了：今日无异常\n解读：平稳本身就是一种小型奇迹。\n建议：宜保持，忌手痒乱改。",
            "fortune": "今日运势：稳中带皮\n主题：适合观察群友，不适合主动跳进战场。\n宜：先备份\n忌：边急边改配置",
            "persona": "今日人设：赛博树洞管理员\n今天负责接住废话、怪话和半夜突然的 emo。",
            "abstract": "抽象指数：42/100\n结论：有一点小火花，但还没到群聊博物馆级别。",
            "profile": "群友小档案还在生成中：样本太少，再多聊几句我就能端出赛博画像。",
            "daily_report": "群聊日报启动失败：今天的样本还不够，群友再冒泡几句我就能写日报。",
            "qzone": "空间侦探启动：这条动态看起来有点故事，但证据不足，建议补一句原文让我锐评。",
        }
        return fallback_map.get(intent) or "我在，想玩什么？可以问我：群里现在啥氛围？"

    def _natural_task(self, text: str, intent: str | None) -> str:
        task_map = {
            "help": (
                "用户在问 FunBox 怎么玩。请用自然聊天方式介绍玩法，告诉用户可以直接说话，"
                "例如“盒子，群里现在啥氛围”。"
            ),
            "status": "用户想查看 FunBox 当前状态。请提醒可用 /funbox状态。",
            "clear_cache": "用户想清理 FunBox 缓存。请提醒可用 /funbox清缓存。",
            "forget_me": "用户想删除自己的 FunBox 样本。请提醒可用 /funbox忘记我。",
            "leaderboard": "用户想看群聊榜单。请说明可用 /群聊榜单、/群聊榜单 抽象、/群聊榜单 梗王、/群聊榜单 问号。",
            "menu": "用户想看 FunBox 菜单。请按常用、个人、群聊、空间、不知道玩啥分组，短短介绍玩法。",
            "recommend": "用户想让你推荐一个当前最适合玩的 FunBox 玩法。请基于上下文只推荐 1 个玩法并说明原因。",
            "random_play": "用户想随机抽一个 FunBox 玩法。请给出玩法名、可直接发送的命令和一句理由。",
            "hot_words": "用户想知道最近群聊热词。请基于上下文列出 3~6 个热词，并给一句好笑结论。",
            "scene": "用户想找最近群聊名场面。请从上下文挑一句最有节目效果的话，并给一句短评。",
            "vibe": "用户想知道群聊氛围。请基于上下文生成氛围雷达，包含类型、读数、结论。",
            "tarot": "用户想抽赛博塔罗。请结合上下文生成卡名、解读、建议。",
            "fortune": "用户想看今日运势。请结合上下文生成今日运势、主题、宜、忌。",
            "persona": "用户想看你今天的人设。请结合上下文生成今日人设、一句描述、口头禅。",
            "abstract": "用户想测抽象/发疯程度。请结合用户原话和上下文给出抽象指数、结论、建议。",
            "profile": "用户想看群友小档案。请基于上下文给出轻松画像，只描述聊天风格，不做真实人格判断。",
            "daily_report": "用户想看群聊日报。请总结最近群聊热词、名场面、气氛和一句今日结论。",
            "qzone": "用户想做空间/说说锐评。请像空间侦探一样分析原话或上下文，轻松吐槽但不要攻击本人。",
        }
        base = task_map.get(intent) or "用户正在自然地和你说话。请像 FunBox 一样接住这句话，短而好笑地回复。"
        return f"用户原话：{text}\n{base}"

    def _menu_text(self, category: str = "") -> str:
        raw = (category or "").strip()
        normalized = raw.lower()
        aliases = {
            "": "",
            "help": "",
            "帮助": "",
            "菜单": "",
            "玩法": "",
            "常用": "常用",
            "基础": "常用",
            "个人": "个人",
            "自己": "个人",
            "群友": "个人",
            "群聊": "群聊",
            "群": "群聊",
            "空间": "空间",
            "说说": "空间",
            "qzone": "空间",
            "不知道": "不知道玩啥",
            "随机": "不知道玩啥",
            "推荐": "不知道玩啥",
            "玩啥": "不知道玩啥",
            "维护": "维护",
            "安全": "维护",
            "隐私": "维护",
            "管理": "维护",
        }
        key = aliases.get(normalized, raw)

        if key in MENU_CATEGORIES:
            lines = [f"FunBox {key}玩法："]
            lines.extend(f"/{name}：{desc}" for name, desc in MENU_CATEGORIES[key])
            lines.append("")
            lines.append("提示：也可以直接叫我，比如“盒子，来点好玩的”。")
            return "\n".join(lines)

        if raw:
            return (
                f"我没找到“{raw}”这个分类。\n"
                "可用分类：常用、个人、群聊、空间、不知道玩啥。\n"
                "例：/趣味帮助 群聊"
            )

        lines = ["FunBox 菜单："]
        for name, entries in MENU_CATEGORIES.items():
            command_names = "、".join(f"/{command}" for command, _ in entries)
            lines.append(f"{name}：{command_names}")
        lines.extend(
            (
                "",
                "记不住就用：/玩点啥 或 /随机玩法",
                "细看分类：/趣味帮助 常用、/趣味帮助 个人、/趣味帮助 群聊、/趣味帮助 空间、/趣味帮助 维护",
            )
        )
        return "\n".join(lines)

    def _recommend_play(self, event: AstrMessageEvent) -> tuple[str, str, str]:
        items = list(self.recent[self._session_key(event)])[-80:]
        if len(items) < 5:
            return ("赛博塔罗", "/赛博塔罗", "样本还少，先抽一张赛博塔罗最不容易冷场。")

        joined = "\n".join(item.get("text", "") for item in items)
        laugh = len(re.findall(r"哈|草|笑|乐|绷|hhh|233|蚌", joined, re.I))
        question = joined.count("?") + joined.count("？")
        exclaim = joined.count("!") + joined.count("！")
        speakers = {item.get("sender_id") for item in items if item.get("sender_id")}
        long_msgs = sum(1 for item in items if len(item.get("text", "")) >= 35)

        if laugh >= 5:
            return ("名场面", "/名场面", "笑点已经冒头了，适合从群里捞一句节目效果。")
        if question >= 6:
            return ("氛围雷达", "/氛围雷达", "问号浓度偏高，适合扫一下群聊空气。")
        if len(items) >= 25 and len(speakers) >= 3:
            return ("群聊日报", "/群聊日报", "样本够了，适合直接生成一份群聊日报。")
        if long_msgs >= 6:
            return ("群聊热词", "/群聊热词", "长消息偏多，先抓关键词比较有意思。")
        if exclaim >= 5:
            return ("抽象指数", "/抽象指数", "感叹号能量偏高，适合测一下抽象读数。")
        return ("今日人设", "/今日人设", "气氛比较平稳，先给 bot 定个今日人设再开玩。")

    def _recommend_text(self, event: AstrMessageEvent) -> str:
        name, command, reason = self._recommend_play(event)
        return (
            "我建议现在玩：\n"
            f"{command}\n"
            f"原因：{reason}\n"
            "如果想交给命运：/随机玩法"
        )

    def _random_play_text(self, event: AstrMessageEvent) -> str:
        rng = self._rng(event, "random_play")
        name, example, reason = rng.choice(PLAY_EXAMPLES)
        return (
            f"随机玩法：{name}\n"
            f"直接发：{example}\n"
            f"为什么它有戏：{reason}"
        )

    def _status_text(self, event: AstrMessageEvent) -> str:
        session_key = self._session_key(event)
        recent_count = len(self.recent[session_key])
        profile_count = len(self.profiles[session_key])
        addressed_mode = "只在叫到 bot 时自然回复" if self.only_when_addressed else "明显趣味请求也会自然回复"
        llm_mode = "开启" if self.enable_llm else "关闭，使用模板兜底"
        auto_daily = (
            f"开启，{self.daily_report_hour} 点后每日一次"
            if self.enable_auto_daily
            else "关闭"
        )
        return (
            "FunBox 状态：\n"
            f"最近消息样本：{recent_count}/{self.max_cache_messages}\n"
            f"群友小档案：{profile_count} 个临时样本\n"
            f"LLM 生成：{llm_mode}\n"
            f"自然回复：{addressed_mode}，冷却 {self.natural_cooldown_seconds}s\n"
            f"自动日报：{auto_daily}\n"
            "隐私：所有样本只存在内存里，可用 /funbox清缓存 或 /funbox忘记我"
        )

    def _clear_session_cache(self, event: AstrMessageEvent) -> tuple[int, int]:
        session_key = self._session_key(event)
        recent_count = len(self.recent[session_key])
        profile_count = len(self.profiles[session_key])
        self.recent[session_key].clear()
        self.profiles[session_key].clear()
        self.natural_last_reply_at.pop(session_key, None)
        self.daily_report_sent.pop(session_key, None)
        return recent_count, profile_count

    def _forget_sender(self, event: AstrMessageEvent) -> tuple[int, bool]:
        session_key = self._session_key(event)
        sender_id = self._sender_id(event)
        items = self.recent[session_key]
        kept = [item for item in items if item.get("sender_id") != sender_id]
        removed = len(items) - len(kept)
        items.clear()
        items.extend(kept)
        had_profile = sender_id in self.profiles[session_key]
        self.profiles[session_key].pop(sender_id, None)
        return removed, had_profile

    def _leaderboard_text(self, event: AstrMessageEvent, kind: str = "") -> str:
        session_key = self._session_key(event)
        profiles = self.profiles[session_key]
        if not profiles:
            return "群聊榜单还没有样本。先让群友聊几句，我再开始颁奖。"

        raw = (kind or "").strip()
        normalized = raw.lower()
        if not normalized or normalized in {"榜单", "排行", "排行榜", "群聊榜单"}:
            normalized = "综合"

        if any(word in normalized for word in ("抽象", "发疯")):
            title = "今日抽象王"
            key_name = "抽象峰值"

            def score(profile: dict) -> int:
                return int(profile.get("abstract_peak", 0))

        elif any(word in normalized for word in ("梗", "笑", "乐")):
            title = "今日梗王"
            key_name = "笑点读数"

            def score(profile: dict) -> int:
                return int(profile.get("laugh_count", 0))

        elif any(word in normalized for word in ("问号", "问题")):
            title = "今日问号王"
            key_name = "问号读数"

            def score(profile: dict) -> int:
                return int(profile.get("question_count", 0))

        else:
            title = "群聊综合榜"
            key_name = "节目效果"

            def score(profile: dict) -> int:
                count = int(profile.get("message_count", 0))
                return (
                    int(profile.get("abstract_peak", 0))
                    + int(profile.get("laugh_count", 0)) * 12
                    + int(profile.get("question_count", 0)) * 6
                    + int(profile.get("long_count", 0)) * 5
                    + min(count, 30)
                )

        ranked = sorted(
            ((sender_id, profile, score(profile)) for sender_id, profile in profiles.items()),
            key=lambda item: item[2],
            reverse=True,
        )
        ranked = [item for item in ranked if item[2] > 0][:5]
        if not ranked:
            return "群聊榜单暂时没有有效读数。大家聊得太像正常人了，我有点不适应。"

        medals = ("1.", "2.", "3.", "4.", "5.")
        lines = [f"{title}："]
        for index, (_, profile, value) in enumerate(ranked):
            name = profile.get("last_name", "某位群友")
            count = int(profile.get("message_count", 0))
            lines.append(f"{medals[index]} {name}：{key_name} {value}，样本 {count} 条")

        lines.extend(
            (
                "",
                "说明：只基于 FunBox 内存里的最近聊天样本，纯节目效果，不代表真实人格。",
                "想清数据：/funbox清缓存；只删自己：/funbox忘记我",
            )
        )
        return "\n".join(lines)

    def _update_profile(self, event: AstrMessageEvent, text: str) -> None:
        if not self.enable_profiles or not text:
            return

        session_key = self._session_key(event)
        sender_id = self._sender_id(event)
        sender_name = self._sender_name(event)
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
        profile = self.profiles[session_key].setdefault(
            sender_id,
            {
                "message_count": 0,
                "last_name": sender_name,
                "last_text": "",
                "last_active": "",
                "abstract_total": 0,
                "abstract_peak": 0,
                "laugh_count": 0,
                "question_count": 0,
                "exclaim_count": 0,
                "long_count": 0,
            },
        )

        score, _ = self._abstract_score(text)
        profile["message_count"] += 1
        profile["last_name"] = sender_name
        profile["last_text"] = text
        profile["last_active"] = now_text
        profile["abstract_total"] += score
        profile["abstract_peak"] = max(int(profile.get("abstract_peak", 0)), score)
        profile["laugh_count"] += len(re.findall(r"哈|草|笑|乐|绷|hhh|233|蚌", text, re.I))
        profile["question_count"] += text.count("?") + text.count("？")
        profile["exclaim_count"] += text.count("!") + text.count("！")
        profile["long_count"] += int(len(text) >= 35)

    def _match_profile(self, event: AstrMessageEvent, query: str) -> tuple[str | None, dict | None]:
        profiles = self.profiles[self._session_key(event)]
        if not query:
            sender_id = self._sender_id(event)
            return sender_id, profiles.get(sender_id)

        needle = self._normalize_bot_name(query)
        for sender_id, profile in profiles.items():
            name = self._normalize_bot_name(profile.get("last_name", ""))
            if needle and (needle in self._normalize_bot_name(sender_id) or needle in name):
                return sender_id, profile
        return None, None

    def _profile_fallback(self, sender_id: str, profile: dict) -> str:
        count = max(1, int(profile.get("message_count", 0)))
        avg_abstract = int(profile.get("abstract_total", 0) / count)
        peak = int(profile.get("abstract_peak", 0))
        laugh = int(profile.get("laugh_count", 0))
        questions = int(profile.get("question_count", 0))
        long_count = int(profile.get("long_count", 0))

        if avg_abstract >= 62 or peak >= 85:
            tag = "抽象火花携带者"
            read = "偶尔一句话就能把群聊空气拧成麻花。"
        elif laugh >= max(3, count // 5):
            tag = "笑点扩散源"
            read = "很擅长让气氛轻轻往发癫方向滑。"
        elif questions >= max(4, count // 4):
            tag = "问题雷达"
            read = "经常负责把大家脑子里的问号具象化。"
        elif long_count >= max(2, count // 5):
            tag = "认真输出型选手"
            read = "不是每次都短打，有时会真的认真把话讲完整。"
        else:
            tag = "稳定冒泡群友"
            read = "存在感不一定最大，但属于群聊生态里的稳定像素点。"

        return (
            f"群友小档案：{profile.get('last_name', sender_id)}\n"
            f"标签：{tag}\n"
            f"样本：{count} 条，抽象均值 {avg_abstract}/100，峰值 {peak}/100\n"
            f"最近：{profile.get('last_text', '暂无')}\n"
            f"观察：{read}"
        )

    def _hot_word_counts(self, items: list[dict], *, top: int = 8) -> list[tuple[str, int]]:
        joined = " ".join(item.get("text", "") for item in items)
        words = re.findall(r"[\u4e00-\u9fa5]{2,6}|[a-zA-Z0-9_]{3,}", joined)
        stop_words = {
            "这个",
            "那个",
            "我们",
            "你们",
            "他们",
            "哈哈",
            "可以",
            "不是",
            "然后",
            "什么",
            "一下",
            "感觉",
            "真的",
            "今天",
            "最近",
            "就是",
        }
        counter = Counter(
            word.lower()
            for word in words
            if word not in stop_words and not word.isdigit()
        )
        return counter.most_common(top)

    def _scene_score(self, item: dict) -> int:
        text = item.get("text", "")
        return (
            len(text)
            + 8 * len(re.findall(r"哈|草|笑|乐|绷|蚌", text, re.I))
            + 4 * (
                text.count("!")
                + text.count("！")
                + text.count("?")
                + text.count("？")
            )
        )

    def _scene_candidates(self, items: list[dict], *, top: int = 5) -> list[dict]:
        return sorted(items, key=self._scene_score, reverse=True)[:top]

    async def _build_daily_report(self, event: AstrMessageEvent, *, auto: bool = False) -> str:
        items = list(self.recent[self._session_key(event)])[-120:]
        if len(items) < 5:
            return "群聊日报启动失败：今天的样本还不够，群友再冒泡几句我就能写日报。"

        texts = [item.get("text", "") for item in items if item.get("text")]
        joined = "\n".join(texts)
        speakers = {item.get("sender") for item in items if item.get("sender")}
        laugh = len(re.findall(r"哈|草|笑|乐|绷|hhh|233|蚌", joined, re.I))
        question = joined.count("?") + joined.count("？")
        exclaim = joined.count("!") + joined.count("！")
        common = self._hot_word_counts(items, top=6)
        hot_text = "、".join(f"{word} x{count}" for word, count in common) or "暂无明显热词"
        scenes = self._scene_candidates(items[-80:], top=3)
        scene_text = "\n".join(
            f"{item.get('time')} {item.get('sender')}：{item.get('text')}"
            for item in scenes
        ) or "暂无名场面"

        if laugh >= 5:
            mood = "发癫回暖"
        elif question >= 6:
            mood = "集体排障"
        elif exclaim >= 5:
            mood = "能量偏高"
        else:
            mood = "稳定冒泡"

        title = "自动群聊日报" if auto else "群聊日报"
        fallback = (
            f"{title}：{mood}\n"
            f"样本：最近 {len(texts)} 条，约 {len(speakers)} 人参与\n"
            f"热词：{hot_text}\n"
            f"名场面：{scene_text.splitlines()[0] if scene_text else '暂无'}\n"
            "结论：今天这群像一台会自己吐槽的轻量服务器。"
        )
        return await self._generate_with_context(
            event,
            task=(
                f"生成一份{'自动' if auto else ''}群聊日报。要求轻松好笑、不攻击具体群友。\n"
                f"统计：样本 {len(texts)} 条，参与者约 {len(speakers)} 人，"
                f"笑点 {laugh}，问号 {question}，感叹号 {exclaim}，气质 {mood}。\n"
                f"热词：{hot_text}\n"
                f"名场面候选：\n{scene_text}\n"
                "输出格式：群聊日报：xxx\n热词：xxx\n名场面：xxx\n今日结论：xxx"
            ),
            fallback=fallback,
            limit=700,
        )

    def _should_auto_daily(self, event: AstrMessageEvent) -> bool:
        if not self.enable_auto_daily:
            return False

        now = datetime.now()
        if now.hour < self.daily_report_hour:
            return False

        session_key = self._session_key(event)
        today = now.strftime("%Y-%m-%d")
        if self.daily_report_sent.get(session_key) == today:
            return False
        if len(self.recent[session_key]) < 12:
            return False
        return True

    def _space_fallback(self, text: str) -> str:
        score, level = self._abstract_score(text)
        length = len(text)
        if "。" in text or "，" in text or "," in text:
            style = "叙事型"
        elif score >= 65:
            style = "抽象宣言型"
        elif length <= 12:
            style = "谜语人型"
        else:
            style = "轻量碎碎念型"

        return (
            f"空间侦探报告：{style}\n"
            f"抽象读数：{score}/100\n"
            f"案情摘要：{level}\n"
            "锐评：这条像是发给全世界看，但真正懂的人可能只有发的人自己。"
        )

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def remember_group_message(self, event: AstrMessageEvent):
        text = self._clean(self._message_text(event), limit=140)
        if self._is_command_like(text):
            return
        if self._is_self_message(event):
            return

        self._update_profile(event, text)
        self.recent[self._session_key(event)].append(
            {
                "time": datetime.now().strftime("%H:%M"),
                "sender_id": self._sender_id(event),
                "sender": self._sender_name(event),
                "text": text,
            }
        )
        if self._should_auto_daily(event):
            session_key = self._session_key(event)
            self.daily_report_sent[session_key] = datetime.now().strftime("%Y-%m-%d")
            # Keep this listener as a normal coroutine. Yielding here turns the
            # cache collector into an async generator and can trip AstrBot's
            # pipeline cleanup during plugin reload.
            await event.send(event.plain_result(await self._build_daily_report(event, auto=True)))

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def natural_funbox_chat(self, event: AstrMessageEvent):
        if not self.enable_natural_reply:
            return

        text = self._clean(self._message_text(event), limit=240)
        if not text or self._is_command_like(text) or self._is_self_message(event):
            return

        await self._ensure_bot_names(event)
        intent = self._detect_intent(text)
        addressed = self._is_addressed(text)
        if self.only_when_addressed and not addressed:
            return
        if not addressed and not self._looks_like_fun_request(text, intent):
            return
        if not addressed and self.natural_cooldown_seconds > 0:
            session_key = self._session_key(event)
            remaining = (
                self.natural_last_reply_at[session_key]
                + self.natural_cooldown_seconds
                - time.time()
            )
            if remaining > 0:
                return

        if intent in {"help", "menu"}:
            reply = self._menu_text()
        elif intent == "recommend":
            reply = self._recommend_text(event)
        elif intent == "random_play":
            reply = self._random_play_text(event)
        elif intent == "status":
            reply = self._status_text(event)
        elif intent == "leaderboard":
            reply = self._leaderboard_text(event, text)
        elif intent == "clear_cache":
            recent_count, profile_count = self._clear_session_cache(event)
            reply = f"已清理当前会话 FunBox 缓存：消息 {recent_count} 条，小档案 {profile_count} 个。"
        elif intent == "forget_me":
            removed, had_profile = self._forget_sender(event)
            profile_text = "已删除" if had_profile else "原本就没有"
            reply = f"我已经忘记你在当前会话里的最近样本：消息 {removed} 条，小档案{profile_text}。"
        else:
            reply = await self._generate_with_context(
                event,
                task=self._natural_task(text, intent),
                fallback=self._natural_fallback(intent),
            )
        if not addressed:
            self.natural_last_reply_at[self._session_key(event)] = time.time()
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("趣味帮助", alias={"funbox"})
    async def funbox_help(self, event: AstrMessageEvent):
        yield event.plain_result(self._menu_text(self._command_arg(event)))
        event.stop_event()

    @filter.command("趣味菜单", alias={"菜单", "玩法", "功能菜单"})
    async def funbox_menu(self, event: AstrMessageEvent):
        yield event.plain_result(self._menu_text(self._command_arg(event)))
        event.stop_event()

    @filter.command("玩点啥", alias={"来点好玩的", "推荐玩法", "帮我选"})
    async def recommend_play(self, event: AstrMessageEvent):
        yield event.plain_result(self._recommend_text(event))
        event.stop_event()

    @filter.command("随机玩法", alias={"抽玩法", "随机"})
    async def random_play(self, event: AstrMessageEvent):
        yield event.plain_result(self._random_play_text(event))
        event.stop_event()

    @filter.command("funbox状态", alias={"趣味状态", "盒子状态"})
    async def funbox_status(self, event: AstrMessageEvent):
        yield event.plain_result(self._status_text(event))
        event.stop_event()

    @filter.command("funbox清缓存", alias={"趣味清缓存", "盒子清缓存"})
    async def funbox_clear_cache(self, event: AstrMessageEvent):
        recent_count, profile_count = self._clear_session_cache(event)
        yield event.plain_result(
            f"已清理当前会话 FunBox 缓存：消息 {recent_count} 条，小档案 {profile_count} 个。"
        )
        event.stop_event()

    @filter.command("funbox忘记我", alias={"趣味忘记我", "盒子忘记我"})
    async def funbox_forget_me(self, event: AstrMessageEvent):
        removed, had_profile = self._forget_sender(event)
        profile_text = "已删除" if had_profile else "原本就没有"
        yield event.plain_result(
            f"我已经忘记你在当前会话里的最近样本：消息 {removed} 条，小档案{profile_text}。"
        )
        event.stop_event()

    @filter.command("群聊榜单", alias={"抽象王", "梗王", "问号王"})
    async def group_leaderboard(self, event: AstrMessageEvent):
        command = self._message_text(event).strip().split(maxsplit=1)[0].lstrip("/")
        arg = self._command_arg(event) or command
        yield event.plain_result(self._leaderboard_text(event, arg))
        event.stop_event()

    @filter.command("今日人设", alias={"人设", "今日人格"})
    async def persona(self, event: AstrMessageEvent):
        rng = self._rng(event, "persona")
        personas = [
            ("困困猫猫秘书", "回复慢半拍，但会认真把话接住。"),
            ("温柔观察员", "不抢戏，专门负责发现大家话里的小情绪。"),
            ("低电量吐槽机", "电量只有 17%，但嘴还挺硬。"),
            ("群聊小天气预报", "主业预报空气湿度，副业判断谁在阴阳怪气。"),
            ("赛博树洞管理员", "今天负责接住废话、怪话和半夜突然的emo。"),
            ("冷静但护短", "表面很稳，实际看到熟人被欺负会立刻上线。"),
            ("松弛感训练生", "今天的原则是：能不急就不急，能发癫就轻轻发。"),
            ("小型名场面记录仪", "专门捕捉一句话突然变成梗的瞬间。"),
        ]
        catchphrases = [
            "先别急，我闻到瓜味了。",
            "这个气氛有点东西。",
            "收到，正在假装很稳。",
            "我先把这句话存进赛博小本本。",
        ]
        name, desc = rng.choice(personas)
        fallback = f"今日人设：{name}\n{desc}\n今日口头禅：{rng.choice(catchphrases)}"
        reply = await self._generate_with_context(
            event,
            task=(
                "为机器人生成一个“今日人设”。要参考群聊最近的气氛，输出格式：\n"
                "今日人设：xxx\n一句描述：xxx\n今日口头禅：xxx\n"
                f"人设必须贴合当前人格/口吻：{self.persona_style or '跟随 AstrBot 当前人格'}"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("赛博塔罗", alias={"塔罗", "抽卡"})
    async def cyber_tarot(self, event: AstrMessageEvent):
        rng = self._rng(event, "tarot")
        cards = [
            ("缓存雪崩", "事情不是突然变坏的，只是你终于看见它在坏。", "宜清理缓存，忌嘴硬。"),
            ("端口占用", "不是没有路，是有个旧东西蹲在路中间不走。", "宜重启思路，忌重复点击。"),
            ("反向 WebSocket", "你以为你在等待连接，其实连接也在寻找你。", "宜主动一点，忌装没看见。"),
            ("内存水位线", "情绪和 RAM 一样，不能长期 95%。", "宜关掉一个窗口，忌同时开十个念头。"),
            ("Cookie 失效", "有些关系不是断了，只是凭据过期了。", "宜重新登录，忌拿旧答案解释新问题。"),
            ("幽灵进程", "看似已经结束，其实还在后台占用你。", "宜彻底放下，忌假装无所谓。"),
            ("安全组未放行", "不是对方冷漠，是门口保安没认出你。", "宜确认规则，忌自我怀疑。"),
            ("今日无异常", "平稳本身就是一种小型奇迹。", "宜保持，忌手痒乱改。"),
        ]
        card, meaning, advice = rng.choice(cards)
        fallback = f"你抽到了：{card}\n解读：{meaning}\n建议：{advice}"
        reply = await self._generate_with_context(
            event,
            task=(
                "基于最近群聊气氛，生成一张“赛博塔罗”结果。输出格式：\n"
                "你抽到了：xxx\n解读：xxx\n建议：xxx\n"
                "卡名要像技术梗、群聊梗或赛博玄学。"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("今日运势", alias={"运势"})
    async def daily_fortune(self, event: AstrMessageEvent):
        rng = self._rng(event, "fortune")
        levels = ["小吉", "中吉", "大吉", "离谱但吉", "先苦后甜", "稳中带皮"]
        themes = [
            "适合把拖了很久的小事收掉。",
            "适合少说两句，但每句都说到点上。",
            "适合大胆开麦，别让梗过期。",
            "适合清缓存、清桌面、清一点点心事。",
            "适合观察群友，不适合主动跳进战场。",
            "适合写点东西，哪怕只是废话文学。",
        ]
        lucky = ["多喝水", "早点睡", "先备份", "少开新坑", "发一个好笑表情", "把话说完整"]
        unlucky = ["硬撑", "连点三次", "空腹吵架", "不看日志", "边急边改配置", "相信玄学但不看报错"]
        fallback = (
            f"今日运势：{rng.choice(levels)}\n"
            f"主题：{rng.choice(themes)}\n"
            f"宜：{rng.choice(lucky)}\n"
            f"忌：{rng.choice(unlucky)}"
        )
        reply = await self._generate_with_context(
            event,
            task=(
                "基于最近群聊上下文，给当前用户生成今日轻量运势。输出格式：\n"
                "今日运势：xxx\n主题：xxx\n宜：xxx\n忌：xxx"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()

    def _abstract_score(self, text: str) -> tuple[int, str]:
        if not text:
            return 0, "无样本，赛博雷达空转。"

        signals = len(
            re.findall(
                r"哈|草|绷|蚌|典|急|麻|离谱|抽象|我靠|不是|啊+|？|！|\\?|!",
                text,
                re.I,
            )
        )
        punctuation = text.count("？") + text.count("?") + text.count("！") + text.count("!")
        repeat = len(re.findall(r"(.)\1{2,}", text))
        length_bonus = min(len(text) // 8, 18)
        score = min(100, 12 + signals * 9 + punctuation * 4 + repeat * 7 + length_bonus)

        if score >= 85:
            level = "宇宙级抽象，建议封存进群聊博物馆。"
        elif score >= 65:
            level = "高抽象，已经能闻到节目效果。"
        elif score >= 40:
            level = "中等抽象，属于稳定发癫。"
        elif score >= 20:
            level = "轻微抽象，有一点小火花。"
        else:
            level = "很正常，正常得有点可疑。"
        return score, level

    @filter.command("抽象指数", alias={"发疯指数", "抽象评分"})
    async def abstract_index(self, event: AstrMessageEvent):
        text = self._command_arg(event)
        source = "指定内容"
        if not text:
            sender_id = self._sender_id(event)
            items = [
                item["text"]
                for item in self.recent[self._session_key(event)]
                if item.get("sender_id") == sender_id
            ][-8:]
            text = " ".join(items)
            source = "你最近的群聊发言"

        score, level = self._abstract_score(text)
        fallback = f"抽象指数：{score}/100\n样本：{source}\n结论：{level}"
        reply = await self._generate_with_context(
            event,
            task=(
                f"给这段样本算一个抽象指数并写短评。\n"
                f"规则评分：{score}/100\n"
                f"样本来源：{source}\n"
                f"样本文本：{text[:600]}\n"
                "输出格式：抽象指数：xx/100\n结论：xxx\n建议：xxx"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("氛围雷达", alias={"气氛雷达", "群聊雷达"})
    async def vibe_radar(self, event: AstrMessageEvent):
        items = list(self.recent[self._session_key(event)])
        if len(items) < 5:
            yield event.plain_result(
                "氛围雷达启动失败：我刚开机，瓜还没攒够。再聊几句我就能开始胡说八道。"
            )
            event.stop_event()
            return

        texts = [x["text"] for x in items[-50:]]
        speakers = {x["sender"] for x in items[-50:]}
        joined = "\n".join(texts)

        laugh = len(re.findall(r"哈|草|笑|乐|绷|hhh|233|蚌", joined, re.I))
        question = joined.count("?") + joined.count("？")
        exclaim = joined.count("!") + joined.count("！")
        long_msgs = sum(1 for t in texts if len(t) >= 35)

        if laugh >= 5:
            mood = "发癫回暖型"
            read = "大家嘴上很乱，实际气氛挺活，适合接梗。"
        elif question >= 6:
            mood = "集体排查故障型"
            read = "群里现在像临时运维室，谁都想把问题钉死。"
        elif long_msgs >= 8:
            mood = "认真输出型"
            read = "长消息偏多，说明有人真的在认真讲东西。"
        elif exclaim >= 5:
            mood = "能量偏高型"
            read = "标点有点激动，建议先喝水再继续冲。"
        else:
            mood = "轻微冒泡型"
            read = "整体平稳，有人在试探性发言，有人在暗中观察。"

        fallback = (
            f"群聊氛围雷达：{mood}\n"
            f"样本：最近 {len(texts)} 条，约 {len(speakers)} 人参与\n"
            f"读数：笑点 {laugh}，问号 {question}，感叹号 {exclaim}，长消息 {long_msgs}\n"
            f"结论：{read}"
        )
        reply = await self._generate_with_context(
            event,
            task=(
                "基于最近群聊上下文和下面的规则读数，生成一份好笑但不攻击人的群聊氛围雷达。\n"
                f"规则判定：{mood}\n"
                f"样本：最近 {len(texts)} 条，约 {len(speakers)} 人参与\n"
                f"读数：笑点 {laugh}，问号 {question}，感叹号 {exclaim}，长消息 {long_msgs}\n"
                "输出格式：群聊氛围雷达：xxx\n读数：xxx\n结论：xxx"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("群聊热词", alias={"热词"})
    async def hot_words(self, event: AstrMessageEvent):
        items = list(self.recent[self._session_key(event)])
        if len(items) < 5:
            yield event.plain_result("热词雷达启动失败：样本太少，再聊几句我就能抓关键词。")
            event.stop_event()
            return

        joined = " ".join(item["text"] for item in items[-80:])
        words = re.findall(r"[\u4e00-\u9fa5]{2,6}|[a-zA-Z0-9_]{3,}", joined)
        stop_words = {
            "这个",
            "那个",
            "我们",
            "你们",
            "他们",
            "哈哈",
            "可以",
            "不是",
            "然后",
            "什么",
            "一下",
            "感觉",
            "真的",
        }
        counter = Counter(
            word.lower()
            for word in words
            if word not in stop_words and not word.isdigit()
        )
        common = counter.most_common(8)
        if not common:
            yield event.plain_result("群聊热词：暂时抓不到关键词，大家聊得太像风吹过。")
            event.stop_event()
            return

        lines = ["群聊热词雷达："]
        lines.extend(f"{index}. {word} x{count}" for index, (word, count) in enumerate(common, 1))
        fallback = "\n".join(lines)
        reply = await self._generate_with_context(
            event,
            task=(
                "基于最近群聊上下文和热词统计，生成一份短小的群聊热词报告。\n"
                f"热词统计：{', '.join(f'{word} x{count}' for word, count in common)}\n"
                "输出格式：群聊热词雷达：\n1. xxx\n2. xxx\n一句结论：xxx"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("群友小档案", alias={"小档案", "群友档案"})
    async def member_profile(self, event: AstrMessageEvent):
        if not self.enable_profiles:
            yield event.plain_result("群友小档案已在配置里关闭。")
            event.stop_event()
            return

        query = self._command_arg(event)
        sender_id, profile = self._match_profile(event, query)
        if not sender_id or not profile:
            target = query or "你"
            yield event.plain_result(f"暂时没有 {target} 的小档案样本。再聊几句，我就能开始建档。")
            event.stop_event()
            return

        samples = [
            item.get("text", "")
            for item in self.recent[self._session_key(event)]
            if item.get("sender_id") == sender_id and item.get("text")
        ][-8:]
        fallback = self._profile_fallback(sender_id, profile)
        reply = await self._generate_with_context(
            event,
            task=(
                "为群友生成一份轻量小档案，只描述最近聊天风格，不要做真实人格判断，"
                "不要攻击或羞辱对方。\n"
                f"目标：{profile.get('last_name', sender_id)} ({sender_id})\n"
                f"统计兜底：\n{fallback}\n"
                f"最近样本：\n" + "\n".join(samples or ["暂无"])
                + "\n输出格式：群友小档案：xxx\n标签：xxx\n观察：xxx\n一句安全锐评：xxx"
            ),
            fallback=fallback,
            limit=640,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("群聊日报", alias={"今日日报", "今日群聊日报"})
    async def daily_report(self, event: AstrMessageEvent):
        yield event.plain_result(await self._build_daily_report(event))
        event.stop_event()

    @filter.command("空间侦探", alias={"说说锐评", "空间锐评"})
    async def space_detective(self, event: AstrMessageEvent):
        text = self._command_arg(event)
        source = "用户提供的说说内容"
        if not text:
            text = self._recent_context(event, limit=12)
            source = "最近群聊上下文"

        if not text:
            yield event.plain_result("空间侦探启动失败：没看到说说原文。用法：/空间侦探 今天又被生活创飞了")
            event.stop_event()
            return

        fallback = self._space_fallback(text)
        reply = await self._generate_with_context(
            event,
            task=(
                "做一份“空间侦探/说说锐评”。要像读 QQ 空间动态一样分析，但不要攻击本人，"
                "不要泄露隐私，不要鼓励网暴。\n"
                f"来源：{source}\n"
                f"文本：{text[:900]}\n"
                "输出格式：空间侦探报告：xxx\n案情摘要：xxx\n隐藏情绪：xxx\n安全锐评：xxx"
            ),
            fallback=fallback,
            limit=680,
        )
        yield event.plain_result(reply)
        event.stop_event()

    @filter.command("名场面", alias={"今日名场面"})
    async def quote_scene(self, event: AstrMessageEvent):
        items = list(self.recent[self._session_key(event)])
        if not items:
            yield event.plain_result("名场面仓库空空如也。先让群友发点能入史的。")
            event.stop_event()
            return

        def score(item):
            text = item["text"]
            return (
                len(text)
                + 8 * len(re.findall(r"哈|草|笑|乐|绷|蚌", text, re.I))
                + 4 * (
                    text.count("!")
                    + text.count("！")
                    + text.count("?")
                    + text.count("？")
                )
            )

        best = sorted(items[-70:], key=score, reverse=True)[:5]
        rng = self._rng(event, "scene")
        item = rng.choice(best)
        fallback = (
            f"名场面候选：\n"
            f"{item['time']} {item['sender']}：{item['text']}\n"
            f"评语：这句有点东西，建议收入赛博小本本。"
        )
        candidates = "\n".join(
            f"{candidate['time']} {candidate['sender']}：{candidate['text']}"
            for candidate in best
        )
        reply = await self._generate_with_context(
            event,
            task=(
                "从下面候选里挑一句最有节目效果的名场面，并给一句短评。\n"
                f"候选：\n{candidates}\n"
                "输出格式：名场面候选：\n时间 昵称：原句\n评语：xxx"
            ),
            fallback=fallback,
        )
        yield event.plain_result(reply)
        event.stop_event()
