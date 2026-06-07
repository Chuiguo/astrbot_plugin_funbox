from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime
import hashlib
import random
import re
import sqlite3
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

try:
    from quart import jsonify as _quart_jsonify
    from quart import request as _quart_request
except Exception:
    _quart_jsonify = None
    _quart_request = None


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
    "funbox自检",
    "趣味自检",
    "盒子自检",
    "funbox示例",
    "趣味示例",
    "盒子示例",
    "funbox状态",
    "趣味状态",
    "盒子状态",
    "funbox清缓存",
    "趣味清缓存",
    "盒子清缓存",
    "funbox忘记我",
    "趣味忘记我",
    "盒子忘记我",
    "funbox隐私",
    "趣味隐私",
    "盒子隐私",
    "群聊榜单",
    "抽象王",
    "梗王",
    "问号王",
    "梗诞生",
    "记梗",
    "登记梗",
    "梗词典",
    "梗档案",
    "梗回收",
    "梗删除",
    "群聊天气",
    "群聊气象",
    "聊天气象",
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
    "群聊速写",
    "速写",
    "群聊快照",
    "聊天快照",
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
        ("玩点啥", "不知道从哪开始时，让 FunBox 只推荐一个。"),
        ("群聊速写", "把刚刚的聊天截成一张四行小画面。"),
        ("氛围雷达", "看最近群聊气氛。"),
        ("名场面", "捞一句最近最有节目效果的话。"),
    ),
    "个人": (
        ("今日人设", "按 AstrBot 当前人格生成今日状态。"),
        ("赛博塔罗", "抽一张赛博运势卡。"),
        ("群友小档案", "根据最近发言生成轻量聊天画像。"),
        ("今日运势", "抽今天的轻量运势。"),
        ("抽象指数", "测一句话或本人近期发言的抽象程度。"),
    ),
    "群聊": (
        ("群聊速写", "把刚刚的聊天截成一张四行小画面。"),
        ("群聊天气", "把最近群聊气氛报成赛博天气。"),
        ("氛围雷达", "用读数吐槽群聊空气。"),
        ("名场面", "捞一句最近最有节目效果的话。"),
        ("群聊热词", "统计最近反复出现的关键词。"),
        ("群聊日报", "总结最近热词、名场面和气质。"),
        ("群聊榜单", "抽象王、梗王、问号王轻量排行。"),
    ),
    "空间": (
        ("空间侦探", "分析说说/空间动态，安全锐评。"),
    ),
    "不知道玩啥": (
        ("玩点啥", "按上下文推荐一个玩法。"),
        ("随机玩法", "随机抽一个玩法并给示例。"),
    ),
    "梗档案": (
        ("梗诞生", "把一句话登记成群聊梗。"),
        ("梗词典", "查看或搜索已登记的梗。"),
        ("梗回收", "把旧梗拿出来复用。"),
        ("梗删除", "删除一个不想保留的梗。"),
    ),
    "维护": (
        ("funbox自检", "检查 LLM、人格、样本和常用配置。"),
        ("funbox示例", "给出几条装完就能复制测试的命令。"),
        ("funbox状态", "查看当前会话缓存和配置状态。"),
        ("funbox隐私", "说明 FunBox 如何处理临时样本。"),
        ("funbox清缓存", "清掉当前群聊 FunBox 内存样本。"),
        ("funbox忘记我", "删除当前用户在 FunBox 里的最近样本。"),
    ),
}

MENU_OVERVIEW = (
    ("精选", "/玩点啥、/群聊速写、/氛围雷达、/名场面"),
    ("群聊", "/群聊速写、/群聊天气、/群聊日报"),
    ("梗档案", "/梗诞生、/梗词典、/梗回收"),
    ("个人", "/今日人设、/赛博塔罗、/群友小档案"),
    ("维护", "/funbox自检、/funbox隐私"),
)

PLAY_EXAMPLES = (
    ("氛围雷达", "/氛围雷达", "最近聊天有点空气流动，适合扫一下气氛。"),
    ("名场面", "/名场面", "群里有梗味时用它，能捞节目效果。"),
    ("今日人设", "/今日人设", "想看 bot 按当前人格进入什么今日状态时用它。"),
    ("赛博塔罗", "/赛博塔罗", "样本不够或想来点玄学时很好用。"),
    ("FunBox 自检", "/funbox自检", "装完插件后先跑它，看看配置和上下文是不是正常。"),
    ("FunBox 示例", "/funbox示例", "新用户不知道怎么玩时，用它拿测试命令。"),
    ("群友小档案", "/群友小档案", "想看自己最近聊天画像时用它。"),
    ("今日运势", "/今日运势", "适合每天先整点轻量玄学。"),
    ("抽象指数", "/抽象指数 我是不是有点离谱", "适合给一句话测抽象读数。"),
    ("群聊天气", "/群聊天气", "想快速知道群里现在是晴天还是局部发癫时用它。"),
    ("梗诞生", "/梗诞生 这服务器像猫一样不听话", "看到一句有梗的话就登记进群聊文化。"),
    ("梗回收", "/梗回收", "想把旧梗翻出来接一句时用它。"),
    ("群聊热词", "/群聊热词", "最近大家反复念叨同一件事时用它。"),
    ("群聊速写", "/群聊速写", "聊了一小阵但还不够日报时，用它截一张有画面的短切片。"),
    ("群聊日报", "/群聊日报", "群里聊了一阵后，用它收个尾。"),
    ("群聊榜单", "/群聊榜单", "样本多了以后可以看看今天谁最有节目效果。"),
    ("空间侦探", "/空间侦探 今天又被生活创飞了", "想锐评说说/空间文案时用它。"),
)


class FunBoxStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    meaning TEXT NOT NULL,
                    usage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memes_session ON memes(session_key, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memes_creator ON memes(session_key, created_by_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS play_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key TEXT NOT NULL,
                    command_key TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meme_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meme_id INTEGER NOT NULL DEFAULT 0,
                    session_key TEXT NOT NULL,
                    meme_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_name TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_play_usage_command ON play_usage(command_key, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_play_usage_session ON play_usage(session_key, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_meme_events_session ON meme_events(session_key, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_meme_events_meme ON meme_events(meme_id, id)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_meme(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "session_key": row["session_key"],
            "name": row["name"],
            "origin": row["origin"],
            "meaning": row["meaning"],
            "usage": row["usage"],
            "created_at": row["created_at"],
            "created_by_id": row["created_by_id"],
            "created_by": row["created_by"],
            "use_count": int(row["use_count"] or 0),
            "updated_at": row["updated_at"],
        }

    def save_meme(self, session_key: str, entry: dict) -> int:
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO memes (
                    session_key, name, origin, meaning, usage,
                    created_at, created_by_id, created_by, use_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_key,
                    str(entry.get("name", "")),
                    str(entry.get("origin", "")),
                    str(entry.get("meaning", "")),
                    str(entry.get("usage", "")),
                    str(entry.get("created_at", "")),
                    str(entry.get("created_by_id", "")),
                    str(entry.get("created_by", "")),
                    int(entry.get("use_count", 0) or 0),
                    updated_at,
                ),
            )
            return int(cur.lastrowid)

    def load_recent(self, per_session_limit: int) -> dict[str, list[dict]]:
        per_session_limit = max(1, int(per_session_limit or 1))
        grouped: dict[str, list[dict]] = defaultdict(list)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memes ORDER BY session_key ASC, id DESC"
            ).fetchall()
        for row in rows:
            item = self._row_to_meme(row)
            session_items = grouped[item["session_key"]]
            if len(session_items) < per_session_limit:
                session_items.append(item)
        for session_key, items in grouped.items():
            grouped[session_key] = list(reversed(items))
        return grouped

    def list_memes(self, *, query: str = "", session_key: str = "", limit: int = 200) -> list[dict]:
        clauses = []
        params: list[object] = []
        if session_key:
            clauses.append("session_key = ?")
            params.append(session_key)
        if query:
            like = f"%{query}%"
            clauses.append("(name LIKE ? OR origin LIKE ? OR meaning LIKE ? OR usage LIKE ?)")
            params.extend([like, like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit or 200), 500)))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM memes {where} ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_meme(row) for row in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM memes").fetchone()[0] or 0)
            sessions = int(conn.execute("SELECT COUNT(DISTINCT session_key) FROM memes").fetchone()[0] or 0)
            recalled = int(conn.execute("SELECT COALESCE(SUM(use_count), 0) FROM memes").fetchone()[0] or 0)
            events = int(conn.execute("SELECT COUNT(*) FROM meme_events").fetchone()[0] or 0)
            plays = int(conn.execute("SELECT COUNT(*) FROM play_usage").fetchone()[0] or 0)
            last_updated = conn.execute("SELECT MAX(updated_at) FROM memes").fetchone()[0] or ""
            session_rows = conn.execute(
                """
                SELECT session_key, COUNT(*) AS count
                FROM memes
                GROUP BY session_key
                ORDER BY count DESC, session_key ASC
                LIMIT 50
                """
            ).fetchall()
        db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "total_memes": total,
            "session_count": sessions,
            "total_recalls": recalled,
            "total_meme_events": events,
            "total_plays": plays,
            "db_path": str(self.db_path),
            "db_size_bytes": db_size_bytes,
            "last_updated": str(last_updated),
            "sessions": [
                {"session_key": str(row["session_key"]), "count": int(row["count"] or 0)}
                for row in session_rows
            ],
            "ready": self.db_path.exists(),
        }

    def increment_use_count(self, meme_id: int) -> None:
        if not meme_id:
            return
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                "UPDATE memes SET use_count = use_count + 1, updated_at = ? WHERE id = ?",
                (updated_at, int(meme_id)),
            )

    def delete_meme(self, meme_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memes WHERE id = ?", (int(meme_id),)).fetchone()
            if row is None:
                return None
            item = self._row_to_meme(row)
            conn.execute("DELETE FROM memes WHERE id = ?", (int(meme_id),))
            return item

    def clear_memes(self, session_key: str = "") -> int:
        with self._connect() as conn:
            if session_key:
                cur = conn.execute("DELETE FROM memes WHERE session_key = ?", (session_key,))
                conn.execute("DELETE FROM meme_events WHERE session_key = ?", (session_key,))
            else:
                cur = conn.execute("DELETE FROM memes")
                conn.execute("DELETE FROM meme_events")
            return int(cur.rowcount or 0)

    def delete_memes_by_sender(self, session_key: str, sender_id: str) -> int:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM memes WHERE session_key = ? AND created_by_id = ?",
                (session_key, sender_id),
            ).fetchall()
            meme_ids = [int(row["id"] or 0) for row in rows if int(row["id"] or 0)]
            cur = conn.execute(
                "DELETE FROM memes WHERE session_key = ? AND created_by_id = ?",
                (session_key, sender_id),
            )
            conn.execute(
                "DELETE FROM meme_events WHERE session_key = ? AND actor_id = ?",
                (session_key, sender_id),
            )
            if meme_ids:
                placeholders = ",".join("?" for _ in meme_ids)
                conn.execute(
                    f"DELETE FROM meme_events WHERE session_key = ? AND meme_id IN ({placeholders})",
                    [session_key, *meme_ids],
                )
            return int(cur.rowcount or 0)

    @staticmethod
    def _row_to_play_usage(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "session_key": row["session_key"],
            "command_key": row["command_key"],
            "raw_text": row["raw_text"],
            "sender_id": row["sender_id"],
            "sender_name": row["sender_name"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_meme_event(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "meme_id": int(row["meme_id"] or 0),
            "session_key": row["session_key"],
            "meme_name": row["meme_name"],
            "event_type": row["event_type"],
            "actor_id": row["actor_id"],
            "actor_name": row["actor_name"],
            "note": row["note"],
            "created_at": row["created_at"],
        }

    def record_play_usage(
        self,
        *,
        session_key: str,
        command_key: str,
        raw_text: str,
        sender_id: str,
        sender_name: str,
    ) -> None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO play_usage (
                    session_key, command_key, raw_text, sender_id, sender_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_key,
                    command_key,
                    raw_text,
                    sender_id,
                    sender_name,
                    created_at,
                ),
            )

    def play_usage_stats(self, limit: int = 12) -> dict:
        limit = max(1, min(int(limit or 12), 50))
        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM play_usage").fetchone()[0] or 0)
            top_rows = conn.execute(
                """
                SELECT command_key, COUNT(*) AS count, MAX(created_at) AS last_used
                FROM play_usage
                GROUP BY command_key
                ORDER BY count DESC, last_used DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            recent_rows = conn.execute(
                "SELECT * FROM play_usage ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {
            "total_plays": total,
            "top_commands": [
                {
                    "command_key": str(row["command_key"]),
                    "count": int(row["count"] or 0),
                    "last_used": str(row["last_used"] or ""),
                }
                for row in top_rows
            ],
            "recent": [self._row_to_play_usage(row) for row in recent_rows],
        }

    def record_meme_event(
        self,
        *,
        meme_id: int = 0,
        session_key: str,
        meme_name: str,
        event_type: str,
        actor_id: str,
        actor_name: str,
        note: str,
    ) -> None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO meme_events (
                    meme_id, session_key, meme_name, event_type, actor_id, actor_name, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(meme_id or 0),
                    session_key,
                    meme_name,
                    event_type,
                    actor_id,
                    actor_name,
                    note,
                    created_at,
                ),
            )

    def list_meme_events(self, *, session_key: str = "", limit: int = 80) -> list[dict]:
        limit = max(1, min(int(limit or 80), 300))
        clauses = []
        params: list[object] = []
        if session_key:
            clauses.append("session_key = ?")
            params.append(session_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM meme_events {where} ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_meme_event(row) for row in rows]


@register(
    "astrbot_plugin_funbox",
    "chuiguo+codex",
    "安全轻量的群聊趣味工具箱：管理面板、梗档案、群聊天气、隐私控制",
    "1.4.2",
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
                "",
            )
            or ""
        ).strip()
        self.natural_cooldown_seconds = self._config_int(
            "natural_cooldown_seconds",
            180,
            minimum=0,
        )
        self.enable_profiles = self._config_bool("enable_profiles", True)
        self.enable_group_weather = self._config_bool("enable_group_weather", True)
        self.weather_use_llm = self._config_bool("weather_use_llm", True)
        self.enable_leaderboard = self._config_bool("enable_leaderboard", True)
        self.leaderboard_min_samples = self._config_int(
            "leaderboard_min_samples",
            1,
            minimum=1,
        )
        self.enable_space_detective = self._config_bool("enable_space_detective", True)
        self.max_meme_entries = self._config_int(
            "max_meme_entries",
            30,
            minimum=5,
        )
        self.enable_meme_database = self._config_bool("enable_meme_database", True)
        self.dashboard_page_limit = self._config_int(
            "dashboard_page_limit",
            120,
            minimum=20,
        )
        self.dashboard_allow_clear_all = self._config_bool("dashboard_allow_clear_all", False)
        self.enable_usage_stats = self._config_bool("enable_usage_stats", True)
        self.dashboard_timeline_limit = self._config_int(
            "dashboard_timeline_limit",
            80,
            minimum=20,
        )
        self.enable_auto_daily = self._config_bool("enable_auto_daily", False)
        self.daily_report_hour = min(
            23,
            max(0, self._config_int("daily_report_hour", 23, minimum=0)),
        )
        self.recent = defaultdict(lambda: deque(maxlen=self.max_cache_messages))
        self.profiles = defaultdict(dict)
        self.meme_book = defaultdict(lambda: deque(maxlen=self.max_meme_entries))
        self.natural_last_reply_at = defaultdict(float)
        self.daily_report_sent = {}
        self.bot_names = set(NATURAL_NAMES)
        self._bot_login_checked = False
        self.data_dir = Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_funbox"
        self.db_path = self.data_dir / "funbox.db"
        self.store = FunBoxStore(self.db_path)
        self._db_ready = False
        for name in self._config_list("extra_trigger_names", []):
            self._add_bot_name(name)
        self._load_context_bot_names()
        self._register_page_web_apis()
        self._initialize_store()
        logger.info("FunBoxPlugin loaded")

    async def initialize(self):
        self._initialize_store()

    def _initialize_store(self) -> None:
        if not self.enable_meme_database:
            self._db_ready = False
            return
        try:
            self.store.initialize()
            self._db_ready = True
            self._restore_memes_from_db()
        except Exception as e:
            self._db_ready = False
            logger.error(f"FunBox 数据库初始化失败: {e}")

    def _restore_memes_from_db(self) -> None:
        if not self._db_ready:
            return
        grouped = self.store.load_recent(self.max_meme_entries)
        for session_key, items in grouped.items():
            bucket = self.meme_book[session_key]
            bucket.clear()
            bucket.extend(items)

    def _register_page_web_apis(self) -> None:
        if not hasattr(self.context, "register_web_api"):
            return
        routes = (
            ("page/status", self.page_status, ["GET"], "FunBox dashboard status"),
            ("page/memes", self.page_memes, ["GET"], "FunBox dashboard memes"),
            ("page/play-usage", self.page_play_usage, ["GET"], "FunBox dashboard play usage"),
            ("page/meme-events", self.page_meme_events, ["GET"], "FunBox dashboard meme timeline"),
            ("page/delete-meme", self.page_delete_meme, ["POST"], "FunBox dashboard delete meme"),
            ("page/clear-memes", self.page_clear_memes, ["POST"], "FunBox dashboard clear memes"),
        )
        for endpoint, handler, methods, desc in routes:
            try:
                self.context.register_web_api(
                    f"/astrbot_plugin_funbox/{endpoint}",
                    handler,
                    methods,
                    desc,
                )
            except Exception as e:
                logger.debug(f"FunBox 注册 Web API 失败 {endpoint}: {e}")

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

    async def _page_response(self, payload: dict, status: int = 200):
        if _quart_jsonify is None:
            return payload
        response = _quart_jsonify(payload)
        response.status_code = status
        return response

    async def _page_json(self, callback):
        try:
            payload = await callback()
            status = 200
        except Exception as exc:
            logger.exception("funbox page api failed: %s", exc)
            payload = {
                "ok": False,
                "error": {"message": str(exc) or "请求失败"},
            }
            status = 400
        return await self._page_response(payload, status)

    async def _page_query_params(self) -> dict:
        if _quart_request is None:
            return {}
        args = getattr(_quart_request, "args", {}) or {}
        try:
            return {str(key): value for key, value in args.items()}
        except Exception:
            return dict(args)

    async def _page_json_body(self) -> dict:
        if _quart_request is None:
            return {}
        try:
            data = await _quart_request.get_json(silent=True)
        except TypeError:
            data = await _quart_request.get_json()
        return data if isinstance(data, dict) else {}

    def _memory_meme_count(self) -> int:
        return sum(len(items) for items in self.meme_book.values())

    def _drop_memory_meme_by_id(self, meme_id: int) -> dict | None:
        for items in self.meme_book.values():
            kept = []
            removed = None
            for item in items:
                if int(item.get("id") or 0) == int(meme_id):
                    removed = item
                else:
                    kept.append(item)
            if removed is not None:
                items.clear()
                items.extend(kept)
                return removed
        return None

    def _clear_memory_memes(self, session_key: str = "") -> int:
        if session_key:
            count = len(self.meme_book[session_key])
            self.meme_book[session_key].clear()
            return count
        count = self._memory_meme_count()
        for items in self.meme_book.values():
            items.clear()
        return count

    async def _build_page_status(self) -> dict:
        db_stats = self.store.stats() if self._db_ready else {
            "total_memes": 0,
            "session_count": 0,
            "total_recalls": 0,
            "total_meme_events": 0,
            "total_plays": 0,
            "db_path": str(self.db_path),
            "db_size_bytes": 0,
            "last_updated": "",
            "sessions": [],
            "ready": False,
        }
        return {
            "ok": True,
            "data": {
                    "version": "1.4.2",
                "database": db_stats,
                "memory": {
                    "sessions": len(self.recent),
                    "recent_messages": sum(len(items) for items in self.recent.values()),
                    "profiles": sum(len(items) for items in self.profiles.values()),
                    "memes": self._memory_meme_count(),
                },
                "config": {
                    "enable_natural_reply": self.enable_natural_reply,
                    "only_when_addressed": self.only_when_addressed,
                    "enable_llm": self.enable_llm,
                    "enable_group_weather": self.enable_group_weather,
                    "weather_use_llm": self.weather_use_llm,
                    "enable_leaderboard": self.enable_leaderboard,
                    "enable_space_detective": self.enable_space_detective,
                    "enable_auto_daily": self.enable_auto_daily,
                    "enable_meme_database": self.enable_meme_database,
                    "dashboard_page_limit": self.dashboard_page_limit,
                    "dashboard_allow_clear_all": self.dashboard_allow_clear_all,
                    "enable_usage_stats": self.enable_usage_stats,
                    "dashboard_timeline_limit": self.dashboard_timeline_limit,
                    "max_cache_messages": self.max_cache_messages,
                    "max_meme_entries": self.max_meme_entries,
                    "natural_cooldown_seconds": self.natural_cooldown_seconds,
                },
                "commands": [
                    "/funbox自检",
                    "/funbox状态",
                    "/梗诞生 这服务器像猫一样不听话",
                    "/梗词典",
                    "/梗回收",
                    "/群聊天气",
                    "/玩点啥",
                ],
            },
        }

    async def page_status(self):
        return await self._page_json(self._build_page_status)

    async def page_memes(self):
        async def handler():
            params = await self._page_query_params()
            query = str(params.get("q") or "").strip()
            session_key = str(params.get("session_key") or "").strip()
            limit = int(params.get("limit") or self.dashboard_page_limit)
            items = self.store.list_memes(query=query, session_key=session_key, limit=limit) if self._db_ready else []
            return {
                "ok": True,
                "data": {
                    "items": items,
                    "total": len(items),
                    "query": query,
                    "session_key": session_key,
                },
            }

        return await self._page_json(handler)

    async def page_play_usage(self):
        async def handler():
            params = await self._page_query_params()
            limit = int(params.get("limit") or 20)
            usage = self.store.play_usage_stats(limit=limit) if self._db_ready and self.enable_usage_stats else {
                "total_plays": 0,
                "top_commands": [],
                "recent": [],
            }
            return {
                "ok": True,
                "data": usage,
            }

        return await self._page_json(handler)

    async def page_meme_events(self):
        async def handler():
            params = await self._page_query_params()
            session_key = str(params.get("session_key") or "").strip()
            limit = int(params.get("limit") or self.dashboard_timeline_limit)
            items = self.store.list_meme_events(session_key=session_key, limit=limit) if self._db_ready else []
            return {
                "ok": True,
                "data": {
                    "items": items,
                    "total": len(items),
                    "session_key": session_key,
                },
            }

        return await self._page_json(handler)

    async def page_delete_meme(self):
        async def handler():
            body = await self._page_json_body()
            meme_id = int(body.get("id") or 0)
            if meme_id <= 0:
                raise ValueError("缺少梗 ID")
            removed = self.store.delete_meme(meme_id) if self._db_ready else None
            if removed and self._db_ready:
                self.store.record_meme_event(
                    meme_id=int(removed.get("id") or 0),
                    session_key=str(removed.get("session_key") or ""),
                    meme_name=str(removed.get("name") or ""),
                    event_type="delete",
                    actor_id="dashboard",
                    actor_name="管理面板",
                    note="从管理面板删除梗档案",
                )
            self._drop_memory_meme_by_id(meme_id)
            return {
                "ok": True,
                "data": {
                    "removed": removed,
                },
            }

        return await self._page_json(handler)

    async def page_clear_memes(self):
        async def handler():
            body = await self._page_json_body()
            session_key = str(body.get("session_key") or "").strip()
            if not session_key and not self.dashboard_allow_clear_all:
                raise ValueError("面板未开启清空全部梗档案权限，请先填写会话或在配置中开启 dashboard_allow_clear_all")
            db_removed = self.store.clear_memes(session_key) if self._db_ready else 0
            memory_removed = self._clear_memory_memes(session_key)
            return {
                "ok": True,
                "data": {
                    "db_removed": db_removed,
                    "memory_removed": memory_removed,
                    "session_key": session_key,
                },
            }

        return await self._page_json(handler)

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

    def _command_key_from_text(self, text: str) -> str:
        raw = self._clean(text, limit=80)
        if not raw:
            return "未知玩法"
        first = raw.split(maxsplit=1)[0].strip().lstrip("/!！.。#")
        return first or "自然触发"

    def _record_play_usage(self, event: AstrMessageEvent, command_key: str, raw_text: str = "") -> None:
        if not self._db_ready or not self.enable_usage_stats:
            return
        try:
            self.store.record_play_usage(
                session_key=self._session_key(event),
                command_key=self._clean(command_key, limit=40),
                raw_text=self._clean(raw_text or self._message_text(event), limit=160),
                sender_id=self._sender_id(event),
                sender_name=self._sender_name(event),
            )
        except Exception as e:
            logger.debug(f"FunBox 记录玩法热度失败: {e}")

    def _record_natural_play_usage(self, event: AstrMessageEvent, intent: str | None, raw_text: str) -> None:
        intent_names = {
            "help": "自然:帮助",
            "menu": "自然:菜单",
            "self_check": "自然:自检",
            "examples": "自然:示例",
            "recommend": "自然:推荐玩法",
            "random_play": "自然:随机玩法",
            "status": "自然:状态",
            "privacy": "自然:隐私",
            "leaderboard": "自然:群聊榜单",
            "meme_birth": "自然:梗诞生",
            "meme_dictionary": "自然:梗词典",
            "meme_recall": "自然:梗回收",
            "weather": "自然:群聊天气",
            "qzone": "自然:空间侦探",
            "clear_cache": "自然:清缓存",
            "forget_me": "自然:忘记我",
            "hot_words": "自然:群聊热词",
            "snapshot": "自然:群聊速写",
            "scene": "自然:名场面",
            "vibe": "自然:氛围雷达",
            "tarot": "自然:赛博塔罗",
            "fortune": "自然:今日运势",
            "persona": "自然:今日人设",
            "abstract": "自然:抽象指数",
            "profile": "自然:群友小档案",
            "daily_report": "自然:群聊日报",
        }
        self._record_play_usage(event, intent_names.get(intent or "", "自然:闲聊触发"), raw_text)

    def _record_meme_event(self, event: AstrMessageEvent, item: dict, event_type: str, note: str) -> None:
        if not self._db_ready:
            return
        try:
            self.store.record_meme_event(
                meme_id=int(item.get("id") or 0),
                session_key=self._session_key(event),
                meme_name=self._clean(str(item.get("name") or ""), limit=40),
                event_type=event_type,
                actor_id=self._sender_id(event),
                actor_name=self._sender_name(event),
                note=self._clean(note, limit=180),
            )
        except Exception as e:
            logger.debug(f"FunBox 记录梗事件失败: {e}")

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
        persona_style = self.persona_style
        astrbot_persona = await self._current_persona_prompt(event)
        persona_instruction = (
            f"AstrBot 当前会话人格（最高优先级）：\n{astrbot_persona[:1200]}\n"
            if astrbot_persona
            else "AstrBot 当前会话人格：未读取到。保持中性、简短、自然，不自行设定新人格。\n"
        )
        system_prompt = (
            "你是 AstrBot 的 FunBox 趣味插件，只负责把玩法结果整理成中文短回复。\n"
            "人格和角色必须跟随 AstrBot 当前会话人格；不要给自己新增固定人设。\n"
            "你要基于最近群聊上下文生成中文短回复。不要泄露隐私，不做人身攻击，"
            "不要挑起争吵，不要输出黄赌毒或仇恨内容。\n"
            "风格：短、自然、有梗但不攻击人。\n"
            f"{persona_instruction}"
        )
        if persona_style:
            system_prompt += f"可选口吻提示（低优先级，不得覆盖 AstrBot 人格）：{persona_style}\n"
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
            ("self_check", ("funbox自检", "趣味自检", "盒子自检", "自检一下", "检查一下", "哪里坏了")),
            ("examples", ("funbox示例", "趣味示例", "盒子示例", "测试命令", "给我示例", "怎么玩示例")),
            ("status", ("funbox状态", "趣味状态", "盒子状态", "状态怎么样", "缓存多少")),
            ("privacy", ("funbox隐私", "趣味隐私", "盒子隐私", "隐私说明", "你记了什么", "会不会存")),
            ("clear_cache", ("funbox清缓存", "趣味清缓存", "盒子清缓存", "清缓存", "清掉缓存", "清空样本")),
            ("forget_me", ("funbox忘记我", "趣味忘记我", "盒子忘记我", "忘记我", "删掉我的样本")),
            ("leaderboard", ("群聊榜单", "排行榜", "抽象王", "梗王", "问号王", "今日榜单")),
            ("meme_birth", ("梗诞生", "记梗", "登记梗", "收录这个梗", "这个有梗")),
            ("meme_dictionary", ("梗词典", "梗档案", "查梗", "有哪些梗")),
            ("meme_recall", ("梗回收", "回收旧梗", "翻旧梗", "用个旧梗")),
            ("meme_delete", ("梗删除", "删除梗", "删梗")),
            ("recommend", ("来点好玩的", "玩点啥", "帮我选", "推荐玩法", "推荐一个", "现在玩啥")),
            ("random_play", ("随机玩法", "抽玩法", "随机一个", "随便来一个", "交给命运")),
            ("menu", ("菜单", "玩法列表", "有哪些玩法", "功能列表")),
            ("help", ("帮助", "怎么用", "你会什么", "funbox")),
            ("profile", ("小档案", "群友档案", "群友画像", "我的档案", "给我建档")),
            ("daily_report", ("日报", "今日总结", "今天群里", "群聊总结")),
            ("snapshot", ("速写", "群聊速写", "快照", "聊天快照", "群聊切片", "刚刚聊了啥")),
            ("weather", ("群聊天气", "群聊气象", "聊天气象", "天气预报", "今天群里天气")),
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

    def _loose_phrase_pattern(self, phrase: str) -> str:
        return r"\s*".join(re.escape(ch) for ch in phrase if not ch.isspace())

    def _strip_address_prefix(self, text: str) -> str:
        cleaned = text.strip()
        for name in sorted(self.bot_names, key=len, reverse=True):
            if not name:
                continue
            pattern = self._loose_phrase_pattern(name)
            cleaned = re.sub(
                rf"^\s*{pattern}\s*[,，:：、]?\s*",
                "",
                cleaned,
                flags=re.I,
            )
        return cleaned.strip()

    def _natural_payload(self, text: str, keywords: tuple[str, ...]) -> str:
        cleaned = self._strip_address_prefix(text)
        for keyword in sorted(keywords, key=len, reverse=True):
            pattern = self._loose_phrase_pattern(keyword)
            updated = re.sub(
                rf"^\s*(?:帮我|给我|请|麻烦)?\s*{pattern}\s*[:：,，、-]?\s*",
                "",
                cleaned,
                flags=re.I,
            ).strip()
            if updated != cleaned:
                return updated
        return cleaned

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
                "记",
                "查",
                "删",
                "回收",
            )
        )

    def _natural_fallback(self, intent: str | None) -> str:
        fallback_map = {
            "help": (
                "FunBox 可用玩法：今日人设、赛博塔罗、氛围雷达、名场面、"
                "梗档案、今日运势、抽象指数、群聊热词。你也可以直接叫我的昵称，例如：群里现在啥氛围？"
            ),
            "self_check": "请发送 /funbox自检，我会检查 LLM、人格、样本和配置状态。",
            "examples": "请发送 /funbox示例，我会给你几条可以直接复制的测试命令。",
            "status": "FunBox 状态可以用 /funbox状态 查看。",
            "privacy": "FunBox 最近群聊样本只在内存里；梗档案默认写入本地 SQLite，可用 /funbox清缓存 或 /funbox忘记我 清理。",
            "clear_cache": "要清当前会话缓存，请发送 /funbox清缓存。",
            "forget_me": "要删除你的最近样本，请发送 /funbox忘记我。",
            "leaderboard": "群聊榜单还没有样本。先让群友聊几句，我再开始颁奖。",
            "meme_birth": "要登记梗，请发送：/梗诞生 这服务器像猫一样不听话",
            "meme_dictionary": "梗词典还是空的。看到有意思的话可以用 /梗诞生 登记。",
            "meme_recall": "梗档案还是空的，暂无旧梗可回收。",
            "meme_delete": "要删除梗，请发送：/梗删除 梗名",
            "menu": self._menu_text(),
            "recommend": "我建议现在玩：/赛博塔罗\n原因：样本还少，先抽一张赛博玄学不冷场。",
            "random_play": "随机玩法：/氛围雷达\n直接发它，我来一本正经地扫一下群聊空气。",
            "snapshot": "现在还太安静，速写纸上只有两三笔。再聊几句，我就能截一张有画面的群聊切片。",
            "hot_words": "我还没攒够上下文，等群里再聊几句我就能抓热词。",
            "scene": "名场面仓库还没攒起来，先让群友发点能入史的。",
            "vibe": "氛围雷达正在预热。再聊几句，我就能开始一本正经地胡说八道。",
            "tarot": "你抽到了：今日无异常\n解读：平稳本身就是一种小型奇迹。\n建议：宜保持，忌手痒乱改。",
            "fortune": "今日运势：稳中带皮\n主题：适合观察群友，不适合主动跳进战场。\n宜：先备份\n忌：边急边改配置",
            "persona": "今日状态：已按 AstrBot 当前人格待机\n一句描述：不额外换皮，只把当前角色发挥得更顺手。",
            "abstract": "抽象指数：42/100\n结论：有一点小火花，但还没到群聊博物馆级别。",
            "profile": "群友小档案还在生成中：样本太少，再多聊几句我就能端出赛博画像。",
            "daily_report": "群聊日报启动失败：今天的样本还不够，群友再冒泡几句我就能写日报。",
            "weather": "群聊天气：样本不足\n天气：刚开机的小晴天\n建议：再聊几句，我就能报局部发癫概率。",
            "qzone": "空间侦探启动：这条动态看起来有点故事，但证据不足，建议补一句原文让我锐评。",
        }
        return fallback_map.get(intent) or "我在，想玩什么？可以问我：群里现在啥氛围？"

    def _natural_task(self, text: str, intent: str | None) -> str:
        task_map = {
            "help": (
                "用户在问 FunBox 怎么玩。请用自然聊天方式介绍玩法，告诉用户可以直接说话，"
                "例如“盒子，群里现在啥氛围”。"
            ),
            "self_check": "用户想让 FunBox 自检。请提醒可用 /funbox自检。",
            "examples": "用户想要 FunBox 测试示例。请提醒可用 /funbox示例。",
            "status": "用户想查看 FunBox 当前状态。请提醒可用 /funbox状态。",
            "privacy": "用户想了解 FunBox 隐私说明。请简短说明最近消息和小档案只在内存里，梗档案默认写入本地 SQLite，可清缓存和忘记我。",
            "clear_cache": "用户想清理 FunBox 缓存。请提醒可用 /funbox清缓存。",
            "forget_me": "用户想删除自己的 FunBox 样本。请提醒可用 /funbox忘记我。",
            "leaderboard": "用户想看群聊榜单。请说明可用 /群聊榜单、/群聊榜单 抽象、/群聊榜单 梗王、/群聊榜单 问号。",
            "meme_birth": "用户想把一句话登记成群聊梗。请提醒可用 /梗诞生 内容。",
            "meme_dictionary": "用户想看梗词典。请提醒可用 /梗词典。",
            "meme_recall": "用户想回收旧梗。请提醒可用 /梗回收。",
            "meme_delete": "用户想删除梗。请提醒可用 /梗删除 梗名。",
            "menu": "用户想看 FunBox 菜单。请给精选入口，不要铺满所有命令；提醒可用 /趣味帮助 分类 查看完整分类。",
            "recommend": "用户想让你推荐一个当前最适合玩的 FunBox 玩法。请基于上下文只推荐 1 个玩法并说明原因。",
            "random_play": "用户想随机抽一个 FunBox 玩法。请给出玩法名、可直接发送的命令和一句理由。",
            "snapshot": "用户想看最近群聊速写。请把最近聊天写成一张短小切片：标题、画面、镜头、旁白，不要写成日报或总结。",
            "hot_words": "用户想知道最近群聊热词。请基于上下文列出 3~6 个热词，并给一句好笑结论。",
            "scene": "用户想找最近群聊名场面。请从上下文挑一句最有节目效果的话，并给一句短评。",
            "vibe": "用户想知道群聊氛围。请基于上下文生成氛围雷达，包含类型、读数、结论。",
            "tarot": "用户想抽赛博塔罗。请结合上下文生成卡名、解读、建议。",
            "fortune": "用户想看今日运势。请结合上下文生成今日运势、主题、宜、忌。",
            "persona": "用户想看你今天的状态。请严格沿用 AstrBot 当前人格，不新增固定人设，生成今日状态、一句描述、口头禅。",
            "abstract": "用户想测抽象/发疯程度。请结合用户原话和上下文给出抽象指数、结论、建议。",
            "profile": "用户想看群友小档案。请基于上下文给出轻松画像，只描述聊天风格，不做真实人格判断。",
            "daily_report": "用户想看群聊日报。请总结最近群聊热词、名场面、气氛和一句今日结论。",
            "weather": "用户想看群聊天气。请把最近群聊气氛写成天气预报，包含天气、温度、风向、预警、建议。",
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
            "梗": "梗档案",
            "梗档案": "梗档案",
            "梗词典": "梗档案",
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
                "可用分类：常用、群聊、个人、梗档案、空间、维护。\n"
                "例：/趣味帮助 群聊"
            )

        lines = ["FunBox 菜单："]
        lines.extend(f"{name}：{commands}" for name, commands in MENU_OVERVIEW)
        lines.extend(
            (
                "",
                "想少想：/玩点啥",
                "想完整：/趣味帮助 群聊、/趣味帮助 梗档案、/趣味帮助 维护",
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
        if exclaim >= 5:
            return ("群聊天气", "/群聊天气", "感叹号能量偏高，适合报一份赛博天气预报。")
        if len(items) >= 25 and len(speakers) >= 3:
            return ("群聊日报", "/群聊日报", "样本够了，适合直接生成一份群聊日报。")
        if len(items) >= 10:
            return ("群聊速写", "/群聊速写", "样本刚好够一张小切片，比日报轻，适合趁热截一帧。")
        if long_msgs >= 6:
            return ("群聊热词", "/群聊热词", "长消息偏多，先抓关键词比较有意思。")
        return ("今日人设", "/今日人设", "气氛比较平稳，先看看 bot 当前人格的今日状态。")

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

    def _examples_text(self) -> str:
        return (
            "FunBox 精选测试：\n"
            "1. /funbox自检\n"
            "2. /玩点啥\n"
            "3. /群聊速写\n"
            "4. /氛围雷达\n"
            "5. /梗诞生 这服务器像猫一样不听话\n"
            "6. 盒子，刚刚群里聊了啥？\n"
            "更多分类：/趣味帮助 群聊"
        )

    async def _self_check_text(self, event: AstrMessageEvent) -> str:
        session_key = self._session_key(event)
        recent_count = len(self.recent[session_key])
        profile_count = len(self.profiles[session_key])
        meme_count = len(self.meme_book[session_key])
        provider = self._get_provider(event)
        persona_prompt = await self._current_persona_prompt(event)

        lines = ["FunBox 自检："]
        lines.append(f"插件版本：1.4.2")
        lines.append(f"LLM provider：{'已读取' if provider else '未读取到，LLM 玩法会走模板兜底'}")
        lines.append(f"AstrBot 人格：{'已读取' if persona_prompt else '未读取到，使用中性兜底，不另设新人格'}")
        lines.append(f"最近消息样本：{recent_count}/{self.max_cache_messages}")
        lines.append(f"群友小档案样本：{profile_count} 个")
        lines.append(f"群聊梗档案：{meme_count}/{self.max_meme_entries} 条")
        if self.enable_meme_database:
            lines.append(f"本地数据库：{'可用' if self._db_ready else '不可用'}")
        else:
            lines.append("本地数据库：已在配置里关闭")
        lines.append(f"自然回复：{'开启' if self.enable_natural_reply else '关闭'}")
        lines.append(f"只在叫到 bot 时回复：{'是' if self.only_when_addressed else '否'}")
        lines.append(f"群聊天气：{'开启' if self.enable_group_weather else '关闭'}")
        lines.append(f"群聊榜单：{'开启' if self.enable_leaderboard else '关闭'}，最低样本 {self.leaderboard_min_samples}")
        lines.append(f"空间侦探：{'开启' if self.enable_space_detective else '关闭'}")
        lines.append(f"玩法热度统计：{'开启' if self.enable_usage_stats else '关闭'}")
        lines.append(f"自动日报：{'开启' if self.enable_auto_daily else '关闭'}")

        suggestions = []
        if not provider and self.enable_llm:
            suggestions.append("LLM provider 没读到：上下文生成会退回模板，检查 AstrBot 当前会话模型配置。")
        if recent_count < 5:
            suggestions.append("样本偏少：群里再聊几句后，/群聊天气、/名场面、/群聊榜单 会更准。")
        if self.enable_natural_reply and not self.only_when_addressed:
            suggestions.append("自然回复较主动：如果怕插嘴，建议开启 only_when_addressed。")
        if self.enable_auto_daily:
            suggestions.append("自动日报已开启：它会在到点后群里首次发言时触发，每会话每天一次。")
        if self.enable_group_weather and not self.weather_use_llm:
            suggestions.append("群聊天气已设置为规则模板模式：更省 token，但没那么会整活。")

        if suggestions:
            lines.append("")
            lines.append("建议：")
            lines.extend(f"- {item}" for item in suggestions)
        else:
            lines.append("")
            lines.append("结论：状态不错，可以先试 /群聊天气 或 /玩点啥。")

        return "\n".join(lines)

    def _status_text(self, event: AstrMessageEvent) -> str:
        session_key = self._session_key(event)
        recent_count = len(self.recent[session_key])
        profile_count = len(self.profiles[session_key])
        meme_count = len(self.meme_book[session_key])
        addressed_mode = "只在叫到 bot 时自然回复" if self.only_when_addressed else "明显趣味请求也会自然回复"
        llm_mode = "开启" if self.enable_llm else "关闭，使用模板兜底"
        auto_daily = (
            f"开启，{self.daily_report_hour} 点后每日一次"
            if self.enable_auto_daily
            else "关闭"
        )
        if self.enable_meme_database:
            db_mode = f"{'可用' if self._db_ready else '不可用'}，{self.db_path}"
            privacy_tail = "梗档案会写入 FunBox 本地 SQLite，可用 /funbox清缓存 或 /funbox忘记我"
        else:
            db_mode = "已关闭，梗档案只保存在运行内存"
            privacy_tail = "梗档案只在内存里，重启后会消失"
        return (
            "FunBox 状态：\n"
            f"最近消息样本：{recent_count}/{self.max_cache_messages}\n"
            f"群友小档案：{profile_count} 个临时样本\n"
            f"群聊梗档案：{meme_count}/{self.max_meme_entries} 条\n"
            f"LLM 生成：{llm_mode}\n"
            f"自然回复：{addressed_mode}，冷却 {self.natural_cooldown_seconds}s\n"
            f"群聊天气：{'开启' if self.enable_group_weather else '关闭'}，LLM润色 {'开启' if self.weather_use_llm else '关闭'}\n"
            f"群聊榜单：{'开启' if self.enable_leaderboard else '关闭'}，最低样本 {self.leaderboard_min_samples}\n"
            f"空间侦探：{'开启' if self.enable_space_detective else '关闭'}\n"
            f"玩法热度统计：{'开启' if self.enable_usage_stats else '关闭'}，记忆线加载 {self.dashboard_timeline_limit} 条\n"
            f"自动日报：{auto_daily}\n"
            f"数据库：{db_mode}\n"
            f"隐私：最近消息只在内存里；{privacy_tail}"
        )

    def _privacy_text(self) -> str:
        meme_store = (
            "梗档案会写入 FunBox 本地 SQLite，方便管理面板查看和跨重启保留。"
            if self.enable_meme_database
            else "梗档案数据库已关闭，梗档案只保存在运行内存，重启后会消失。"
        )
        return (
            "FunBox 隐私说明：\n"
            "1. 只缓存当前会话最近消息，用来生成菜单推荐、榜单、小档案、日报和梗档案。\n"
            "2. 最近消息和小档案不写数据库，重启 AstrBot 后会自然消失。\n"
            f"3. {meme_store}\n"
            "4. 玩法热度只记录 FunBox 触发入口，不记录普通聊天内容。\n"
            "5. /funbox清缓存：清掉当前会话所有 FunBox 样本和梗档案。\n"
            "6. /funbox忘记我：删除你在当前会话里的最近样本，以及你创建的梗。\n"
            "7. 榜单、小档案和梗档案都是节目效果，不代表真实人格。"
        )

    def _clear_session_cache(self, event: AstrMessageEvent) -> tuple[int, int, int]:
        session_key = self._session_key(event)
        recent_count = len(self.recent[session_key])
        profile_count = len(self.profiles[session_key])
        meme_count = len(self.meme_book[session_key])
        self.recent[session_key].clear()
        self.profiles[session_key].clear()
        self.meme_book[session_key].clear()
        if self._db_ready:
            meme_count = max(meme_count, self.store.clear_memes(session_key))
        self.natural_last_reply_at.pop(session_key, None)
        self.daily_report_sent.pop(session_key, None)
        return recent_count, profile_count, meme_count

    def _forget_sender(self, event: AstrMessageEvent) -> tuple[int, bool, int]:
        session_key = self._session_key(event)
        sender_id = self._sender_id(event)
        items = self.recent[session_key]
        kept = [item for item in items if item.get("sender_id") != sender_id]
        removed = len(items) - len(kept)
        items.clear()
        items.extend(kept)
        had_profile = sender_id in self.profiles[session_key]
        self.profiles[session_key].pop(sender_id, None)
        memes = self.meme_book[session_key]
        kept_memes = [item for item in memes if item.get("created_by_id") != sender_id]
        meme_removed = len(memes) - len(kept_memes)
        memes.clear()
        memes.extend(kept_memes)
        if self._db_ready:
            meme_removed = max(meme_removed, self.store.delete_memes_by_sender(session_key, sender_id))
        return removed, had_profile, meme_removed

    def _leaderboard_text(self, event: AstrMessageEvent, kind: str = "") -> str:
        if not self.enable_leaderboard:
            return "群聊榜单已在 FunBox 配置里关闭。"

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
        ranked = [
            item
            for item in ranked
            if item[2] > 0 and int(item[1].get("message_count", 0)) >= self.leaderboard_min_samples
        ][:5]
        if not ranked:
            return (
                "群聊榜单暂时没有有效读数。\n"
                f"当前最低样本要求：每人 {self.leaderboard_min_samples} 条。"
            )

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

    def _weather_reading(self, event: AstrMessageEvent) -> dict:
        items = list(self.recent[self._session_key(event)])[-60:]
        texts = [item.get("text", "") for item in items if item.get("text")]
        joined = "\n".join(texts)
        laugh = len(re.findall(r"哈|草|笑|乐|绷|hhh|233|蚌", joined, re.I))
        question = joined.count("?") + joined.count("？")
        exclaim = joined.count("!") + joined.count("！")
        long_msgs = sum(1 for text in texts if len(text) >= 35)
        abstract_score, _ = self._abstract_score(joined[:1000])

        if len(texts) < 5:
            weather = "刚开机小晴天"
            temperature = "22°C"
            wind = "微风，样本不足"
            warning = "暂无预警"
            advice = "再聊几句，我再开始认真胡说。"
        elif laugh >= 6 or abstract_score >= 72:
            weather = "局部发癫，多云转抽象"
            temperature = f"{min(39, 24 + laugh + abstract_score // 18)}°C"
            wind = "梗风偏强，容易把话题吹歪"
            warning = "节目效果黄色预警"
            advice = "适合 /名场面 或 /群聊榜单。"
        elif question >= 6:
            weather = "问号阵雨"
            temperature = f"{24 + min(question, 8)}°C"
            wind = "排障风，方向不稳定"
            warning = "连续追问预警"
            advice = "适合 /氛围雷达，把问号先收编。"
        elif long_msgs >= 6:
            weather = "长文低压槽"
            temperature = "26°C"
            wind = "认真输出风，偶有解释型强对流"
            warning = "信息量偏高"
            advice = "适合 /群聊热词 或 /群聊日报。"
        elif exclaim >= 5:
            weather = "能量热浪"
            temperature = f"{28 + min(exclaim, 9)}°C"
            wind = "感叹号南风"
            warning = "情绪升温预警"
            advice = "先喝水，再继续开麦。"
        else:
            weather = "稳定冒泡，晴间多云"
            temperature = "25°C"
            wind = "轻微路过风"
            warning = "暂无明显异常"
            advice = "适合 /今日人设 或 /赛博塔罗 起个轻梗。"

        return {
            "count": len(texts),
            "laugh": laugh,
            "question": question,
            "exclaim": exclaim,
            "long_msgs": long_msgs,
            "abstract_score": abstract_score,
            "weather": weather,
            "temperature": temperature,
            "wind": wind,
            "warning": warning,
            "advice": advice,
        }

    async def _weather_text(self, event: AstrMessageEvent) -> str:
        if not self.enable_group_weather:
            return "群聊天气已在 FunBox 配置里关闭。"

        reading = self._weather_reading(event)
        fallback = (
            f"群聊天气：{reading['weather']}\n"
            f"温度：{reading['temperature']}\n"
            f"风向：{reading['wind']}\n"
            f"预警：{reading['warning']}\n"
            f"建议：{reading['advice']}"
        )
        if not self.weather_use_llm:
            return fallback

        return await self._generate_with_context(
            event,
            task=(
                "把最近群聊气氛写成一份有节目效果但不攻击人的天气预报。\n"
                f"规则读数：样本 {reading['count']} 条，笑点 {reading['laugh']}，"
                f"问号 {reading['question']}，感叹号 {reading['exclaim']}，"
                f"长消息 {reading['long_msgs']}，抽象读数 {reading['abstract_score']}/100。\n"
                f"规则天气：{reading['weather']}；温度：{reading['temperature']}；"
                f"风向：{reading['wind']}；预警：{reading['warning']}；建议：{reading['advice']}\n"
                "输出格式：群聊天气：xxx\n温度：xxx\n风向：xxx\n预警：xxx\n建议：xxx"
            ),
            fallback=fallback,
            limit=620,
        )

    def _meme_items(self, event: AstrMessageEvent) -> list[dict]:
        return list(self.meme_book[self._session_key(event)])

    def _meme_name_from_text(self, text: str) -> str:
        words = re.findall(r"[\u4e00-\u9fa5]{2,6}|[a-zA-Z0-9_]{3,}", text)
        stop_words = {"这个", "那个", "我们", "你们", "他们", "哈哈", "不是", "什么"}
        picked = next((word for word in words if word not in stop_words), "")
        if picked:
            return f"{picked}学"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:4]
        return f"无名梗{digest}"

    def _parse_meme_reply(self, reply: str, fallback_name: str, fallback_meaning: str) -> tuple[str, str, str]:
        name = fallback_name
        meaning = fallback_meaning
        usage = "适合在类似场景里轻轻回收一下。"
        for line in reply.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(("梗名：", "梗名:")):
                name = line.split("：", 1)[-1].split(":", 1)[-1].strip() or name
            elif line.startswith(("解释：", "解释:")):
                meaning = line.split("：", 1)[-1].split(":", 1)[-1].strip() or meaning
            elif line.startswith(("用法：", "用法:")):
                usage = line.split("：", 1)[-1].split(":", 1)[-1].strip() or usage
        return self._clean(name, limit=24), self._clean(meaning, limit=120), self._clean(usage, limit=120)

    def _find_meme(self, event: AstrMessageEvent, query: str) -> tuple[int, dict] | tuple[None, None]:
        items = self._meme_items(event)
        if not items:
            return None, None
        needle = self._normalize_bot_name(query)
        if not needle:
            return len(items) - 1, items[-1]
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            haystack = self._normalize_bot_name(
                f"{item.get('name', '')} {item.get('origin', '')} {item.get('meaning', '')}"
            )
            if needle in haystack:
                return index, item
        return None, None

    async def _meme_birth_text(self, event: AstrMessageEvent, content: str) -> str:
        content = self._clean(content, limit=160)
        source = "用户指定内容"
        if not content:
            recent = list(self.recent[self._session_key(event)])[-50:]
            if not recent:
                return "梗诞生失败：最近没有可登记的群聊样本。用法：/梗诞生 这服务器像猫一样不听话"
            item = max(recent, key=self._scene_score)
            content = self._clean(item.get("text", ""), limit=160)
            source = f"{item.get('time')} {item.get('sender')}"

        fallback_name = self._meme_name_from_text(content)
        fallback_meaning = "这句话被群聊空气腌入味了，适合作为临时梗保存。"
        fallback = (
            f"梗名：{fallback_name}\n"
            f"出处：{content}\n"
            f"解释：{fallback_meaning}\n"
            "用法：下次遇到类似场面，可以把它拿出来轻轻回收。"
        )
        reply = await self._generate_with_context(
            event,
            task=(
                "把下面这句话登记成群聊梗。不要改变 AstrBot 当前人格，只做梗档案整理。\n"
                f"来源：{source}\n"
                f"原句：{content}\n"
                "输出格式：梗名：xxx\n出处：xxx\n解释：xxx\n用法：xxx"
            ),
            fallback=fallback,
            limit=620,
        )
        name, meaning, usage = self._parse_meme_reply(reply, fallback_name, fallback_meaning)
        session_key = self._session_key(event)
        entry = {
            "name": name,
            "origin": content,
            "meaning": meaning,
            "usage": usage,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "created_by_id": self._sender_id(event),
            "created_by": self._sender_name(event),
            "use_count": 0,
        }
        if self._db_ready:
            try:
                entry["id"] = self.store.save_meme(session_key, entry)
                self._record_meme_event(event, entry, "birth", f"登记梗：{content}")
            except Exception as e:
                logger.warning(f"FunBox 保存梗档案失败: {e}")
        self.meme_book[session_key].append(entry)
        return (
            f"梗诞生：{name}\n"
            f"出处：{content}\n"
            f"解释：{meaning}\n"
            f"用法：{usage}\n"
            f"当前梗档案：{len(self.meme_book[session_key])}/{self.max_meme_entries}"
        )

    def _meme_dictionary_text(self, event: AstrMessageEvent, query: str = "") -> str:
        items = self._meme_items(event)
        if not items:
            return "梗词典还是空的。看到有意思的话可以用：/梗诞生 原句"
        if query:
            needle = self._normalize_bot_name(query)
            items = [
                item
                for item in items
                if needle
                and needle
                in self._normalize_bot_name(
                    f"{item.get('name', '')} {item.get('origin', '')} {item.get('meaning', '')}"
                )
            ]
            if not items:
                return f"梗词典里暂时没搜到：{query}"

        lines = [f"梗词典：共 {len(self.meme_book[self._session_key(event)])} 条"]
        for index, item in enumerate(items[-8:], 1):
            lines.append(
                f"{index}. {item.get('name')}：{item.get('meaning')}（回收 {int(item.get('use_count', 0))} 次）\n"
                f"   出处：{item.get('origin')}"
            )
        lines.append("提示：/梗回收 [梗名] 可以把旧梗翻出来。")
        return "\n".join(lines)

    async def _meme_recall_text(self, event: AstrMessageEvent, query: str = "") -> str:
        _, item = self._find_meme(event, query)
        if not item:
            return "梗回收失败：梗档案还是空的，或没找到这个梗。"
        item["use_count"] = int(item.get("use_count", 0)) + 1
        if self._db_ready:
            try:
                self.store.increment_use_count(int(item.get("id") or 0))
                self._record_meme_event(event, item, "recall", f"回收梗：{item.get('name')}")
            except Exception as e:
                logger.debug(f"FunBox 更新梗使用次数失败: {e}")
        fallback = (
            f"梗回收：{item.get('name')}\n"
            f"旧出处：{item.get('origin')}\n"
            f"这会儿可以这样接：{item.get('usage')}"
        )
        return await self._generate_with_context(
            event,
            task=(
                "把一个旧群聊梗自然回收到当前聊天里。不要解释太长，不要攻击任何人。\n"
                f"梗名：{item.get('name')}\n"
                f"旧出处：{item.get('origin')}\n"
                f"解释：{item.get('meaning')}\n"
                f"用法：{item.get('usage')}\n"
                "输出格式：梗回收：xxx\n这会儿可以这样接：xxx"
            ),
            fallback=fallback,
            limit=520,
        )

    def _meme_delete_text(self, event: AstrMessageEvent, query: str) -> str:
        if not query:
            return "要删除哪个梗？用法：/梗删除 梗名"
        index, item = self._find_meme(event, query)
        if item is None or index is None:
            return f"没找到这个梗：{query}"
        session_key = self._session_key(event)
        items = self._meme_items(event)
        removed = items.pop(index)
        if self._db_ready:
            try:
                self._record_meme_event(event, removed, "delete", f"删除梗：{removed.get('name')}")
                self.store.delete_meme(int(removed.get("id") or 0))
            except Exception as e:
                logger.debug(f"FunBox 删除梗档案失败: {e}")
        self.meme_book[session_key].clear()
        self.meme_book[session_key].extend(items)
        return f"已删除梗：{removed.get('name')}"

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

    def _polish_snapshot_reply(self, text: str, fallback: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
        if not text:
            return fallback
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) <= 4 and any(line.startswith("群聊速写") for line in lines):
            return "\n".join(lines)

        wanted_prefixes = ("群聊速写", "画面：", "镜头：", "旁白：")
        picked: list[str] = []
        for prefix in wanted_prefixes:
            match = next((line for line in lines if line.startswith(prefix)), "")
            if match:
                picked.append(match)
        if len(picked) >= 3:
            return "\n".join(picked[:4])
        return fallback

    async def _build_group_snapshot(self, event: AstrMessageEvent) -> str:
        items = list(self.recent[self._session_key(event)])[-80:]
        if len(items) < 4:
            return "现在还太安静，速写纸上只有两三笔。再聊几句，我就能截一张有画面的群聊切片。"

        texts = [item.get("text", "") for item in items if item.get("text")]
        joined = "\n".join(texts)
        speakers = {item.get("sender") for item in items if item.get("sender")}
        laugh = len(re.findall(r"哈|草|笑|乐|绷|hhh|233|蚌", joined, re.I))
        question = joined.count("?") + joined.count("？")
        exclaim = joined.count("!") + joined.count("！")
        hot_words = self._hot_word_counts(items, top=4)
        hot_text = "、".join(word for word, _ in hot_words) or "暂无明显关键词"
        def short(value: str, limit: int = 54) -> str:
            value = re.sub(r"\s+", " ", str(value or "")).strip()
            return value if len(value) <= limit else value[:limit].rstrip() + "..."

        scenes = self._scene_candidates(items[-50:], top=3)
        scene_text = "\n".join(
            f"{item.get('time')} {item.get('sender')}：{short(item.get('text'), 72)}"
            for item in scenes
        ) or "暂无"

        if laugh >= 4:
            frame = "笑点冒泡"
            image = "几句笑声把屏幕戳出小气泡。"
            aside = "这段像群聊自己给自己加了弹幕。"
        elif question >= 4:
            frame = "集体排障"
            image = "问号排成一小队，大家在给问题找出口。"
            aside = "空气里有一点问号味，适合先把问题摊平。"
        elif exclaim >= 4:
            frame = "能量上扬"
            image = "感叹号把气氛顶高了一点。"
            aside = "标点已经开始踮脚，群聊热度在升。"
        elif len(speakers) >= 4:
            frame = "多人冒泡"
            image = "几个头像轮流亮起，群聊有了小小人声。"
            aside = "大家像陆续上线的小灯，一盏一盏亮起来。"
        else:
            frame = "轻量闲聊"
            image = "聊天像桌角便利贴，轻轻贴了一张。"
            aside = "不算热闹，但已经有一点能被截屏保存的生活噪声。"

        if scenes:
            lens = f"{scenes[0].get('sender')}：{short(scenes[0].get('text'), 64)}"
        else:
            lens = "暂无明显名场面"
        fallback = (
            f"群聊速写｜{frame}\n"
            f"画面：{image}\n"
            f"镜头：{lens}\n"
            f"旁白：{aside}（关键词：{hot_text}）"
        )

        reply = await self._generate_with_context(
            event,
            task=(
                "把最近群聊写成一张精品“群聊速写/聊天快照”。它不是日报，不要长篇总结，"
                "不要列统计，不要像机器人报告；像给刚刚这段聊天截一张轻松、有画面的小切片。\n"
                f"统计：样本 {len(texts)} 条，参与者约 {len(speakers)} 人，"
                f"笑点 {laugh}，问号 {question}，感叹号 {exclaim}，速写类型 {frame}。\n"
                f"关键词素材：{hot_text}\n"
                f"候选镜头：\n{scene_text}\n"
                "固定输出 4 行，不要加 Markdown 加粗，不要额外解释：\n"
                "群聊速写｜2到6字标题\n"
                "画面：一句有画面感的氛围描写\n"
                "镜头：从候选镜头里提炼一句，不要歪曲原意\n"
                "旁白：一句轻松收尾；关键词只作为素材，不单独列一行"
            ),
            fallback=fallback,
            limit=420,
        )
        return self._polish_snapshot_reply(reply, fallback)

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
        if self._is_self_message(event):
            return
        if self._is_command_like(text):
            self._record_play_usage(event, self._command_key_from_text(text), text)
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

        self._record_natural_play_usage(event, intent, text)

        if intent in {"help", "menu"}:
            reply = self._menu_text()
        elif intent == "self_check":
            reply = await self._self_check_text(event)
        elif intent == "examples":
            reply = self._examples_text()
        elif intent == "recommend":
            reply = self._recommend_text(event)
        elif intent == "random_play":
            reply = self._random_play_text(event)
        elif intent == "status":
            reply = self._status_text(event)
        elif intent == "privacy":
            reply = self._privacy_text()
        elif intent == "leaderboard":
            reply = self._leaderboard_text(event, text)
        elif intent == "meme_birth":
            reply = await self._meme_birth_text(
                event,
                self._natural_payload(text, ("梗诞生", "记梗", "登记梗", "收录这个梗", "这个有梗")),
            )
        elif intent == "meme_dictionary":
            reply = self._meme_dictionary_text(
                event,
                self._natural_payload(text, ("梗词典", "梗档案", "查梗", "有哪些梗")),
            )
        elif intent == "meme_recall":
            reply = await self._meme_recall_text(
                event,
                self._natural_payload(text, ("梗回收", "回收旧梗", "翻旧梗", "用个旧梗")),
            )
        elif intent == "meme_delete":
            reply = "删除梗为了防误删，请用明确命令：/梗删除 梗名"
        elif intent == "weather":
            reply = await self._weather_text(event)
        elif intent == "snapshot":
            reply = await self._build_group_snapshot(event)
        elif intent == "qzone" and not self.enable_space_detective:
            reply = "空间侦探已在 FunBox 配置里关闭。"
        elif intent == "clear_cache":
            recent_count, profile_count, meme_count = self._clear_session_cache(event)
            reply = (
                f"已清理当前会话 FunBox 缓存：消息 {recent_count} 条，"
                f"小档案 {profile_count} 个，梗档案 {meme_count} 条。"
            )
        elif intent == "forget_me":
            removed, had_profile, meme_removed = self._forget_sender(event)
            profile_text = "已删除" if had_profile else "原本就没有"
            reply = (
                f"我已经忘记你在当前会话里的最近样本：消息 {removed} 条，"
                f"小档案{profile_text}，你创建的梗 {meme_removed} 条。"
            )
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

    @filter.command("funbox自检", alias={"趣味自检", "盒子自检"})
    async def funbox_self_check(self, event: AstrMessageEvent):
        yield event.plain_result(await self._self_check_text(event))
        event.stop_event()

    @filter.command("funbox示例", alias={"趣味示例", "盒子示例"})
    async def funbox_examples(self, event: AstrMessageEvent):
        yield event.plain_result(self._examples_text())
        event.stop_event()

    @filter.command("funbox状态", alias={"趣味状态", "盒子状态"})
    async def funbox_status(self, event: AstrMessageEvent):
        yield event.plain_result(self._status_text(event))
        event.stop_event()

    @filter.command("funbox隐私", alias={"趣味隐私", "盒子隐私"})
    async def funbox_privacy(self, event: AstrMessageEvent):
        yield event.plain_result(self._privacy_text())
        event.stop_event()

    @filter.command("funbox清缓存", alias={"趣味清缓存", "盒子清缓存"})
    async def funbox_clear_cache(self, event: AstrMessageEvent):
        recent_count, profile_count, meme_count = self._clear_session_cache(event)
        yield event.plain_result(
            f"已清理当前会话 FunBox 缓存：消息 {recent_count} 条，"
            f"小档案 {profile_count} 个，梗档案 {meme_count} 条。"
        )
        event.stop_event()

    @filter.command("funbox忘记我", alias={"趣味忘记我", "盒子忘记我"})
    async def funbox_forget_me(self, event: AstrMessageEvent):
        removed, had_profile, meme_removed = self._forget_sender(event)
        profile_text = "已删除" if had_profile else "原本就没有"
        yield event.plain_result(
            f"我已经忘记你在当前会话里的最近样本：消息 {removed} 条，"
            f"小档案{profile_text}，你创建的梗 {meme_removed} 条。"
        )
        event.stop_event()

    @filter.command("群聊榜单", alias={"抽象王", "梗王", "问号王"})
    async def group_leaderboard(self, event: AstrMessageEvent):
        command = self._message_text(event).strip().split(maxsplit=1)[0].lstrip("/")
        arg = self._command_arg(event) or command
        yield event.plain_result(self._leaderboard_text(event, arg))
        event.stop_event()

    @filter.command("群聊天气", alias={"群聊气象", "聊天气象"})
    async def group_weather(self, event: AstrMessageEvent):
        yield event.plain_result(await self._weather_text(event))
        event.stop_event()

    @filter.command("梗诞生", alias={"记梗", "登记梗"})
    async def meme_birth(self, event: AstrMessageEvent):
        yield event.plain_result(await self._meme_birth_text(event, self._command_arg(event)))
        event.stop_event()

    @filter.command("梗词典", alias={"梗档案"})
    async def meme_dictionary(self, event: AstrMessageEvent):
        yield event.plain_result(self._meme_dictionary_text(event, self._command_arg(event)))
        event.stop_event()

    @filter.command("梗回收")
    async def meme_recall(self, event: AstrMessageEvent):
        yield event.plain_result(await self._meme_recall_text(event, self._command_arg(event)))
        event.stop_event()

    @filter.command("梗删除")
    async def meme_delete(self, event: AstrMessageEvent):
        yield event.plain_result(self._meme_delete_text(event, self._command_arg(event)))
        event.stop_event()

    @filter.command("今日人设", alias={"人设", "今日人格"})
    async def persona(self, event: AstrMessageEvent):
        fallback = (
            "今日状态：沿用 AstrBot 当前人格\n"
            "一句描述：不额外换皮，只把当前角色发挥得更顺手。\n"
            "今日口头禅：我按当前人格来，不抢戏。"
        )
        reply = await self._generate_with_context(
            event,
            task=(
                "为机器人生成一个“今日状态”。必须严格沿用 AstrBot 当前人格，"
                "不要新增猫猫、秘书、树洞、记录仪等固定新人设。\n"
                "输出格式：今日状态：xxx\n一句描述：xxx\n今日口头禅：xxx"
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

    @filter.command("群聊速写", alias={"速写", "群聊快照", "聊天快照"})
    async def group_snapshot(self, event: AstrMessageEvent):
        yield event.plain_result(await self._build_group_snapshot(event))
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
        if not self.enable_space_detective:
            yield event.plain_result("空间侦探已在 FunBox 配置里关闭。")
            event.stop_event()
            return

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

