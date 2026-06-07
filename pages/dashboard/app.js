const bridge = window.AstrBotPluginPage;
const REQUEST_TIMEOUT_MS = 15000;

const state = {
  activeSection: "overview",
  status: null,
  memes: [],
  usage: null,
  timeline: [],
  loading: false,
};

const commandGroups = [
  {
    title: "入口",
    desc: "记不住功能时，从这里开始。",
    items: ["/趣味菜单", "/玩点啥", "/随机玩法", "/funbox示例"],
  },
  {
    title: "梗档案",
    desc: "把群聊里的好笑瞬间沉淀下来。",
    items: ["/梗诞生 这服务器像猫一样不听话", "/梗词典", "/梗回收", "/梗删除 服务器"],
  },
  {
    title: "群聊观察",
    desc: "看气氛、看热词、看今天谁最有节目效果。",
    items: ["/群聊天气", "/氛围雷达", "/名场面", "/群聊热词", "/群聊速写", "/群聊日报", "/群聊榜单"],
  },
  {
    title: "个人玩法",
    desc: "轻量整活，不做真实画像。",
    items: ["/今日人设", "/赛博塔罗", "/今日运势", "/抽象指数 我是不是有点离谱", "/群友小档案"],
  },
  {
    title: "维护",
    desc: "检查配置、隐私说明、清理当前会话样本。",
    items: ["/funbox自检", "/funbox状态", "/funbox隐私", "/funbox清缓存", "/funbox忘记我"],
  },
];

const quickCommands = [
  "/funbox自检",
  "/funbox状态",
  "/funbox隐私",
  "/梗诞生 这服务器像猫一样不听话",
  "/梗词典",
  "/群聊天气",
  "/群聊速写",
];

const el = {
  bridgeState: document.getElementById("bridgeState"),
  sectionTitle: document.getElementById("sectionTitle"),
  notice: document.getElementById("notice"),
  refreshButton: document.getElementById("refreshButton"),
  loadAllMemesButton: document.getElementById("loadAllMemesButton"),
  reloadMemesButton: document.getElementById("reloadMemesButton"),
  reloadUsageButton: document.getElementById("reloadUsageButton"),
  reloadTimelineButton: document.getElementById("reloadTimelineButton"),
  memeSearchForm: document.getElementById("memeSearchForm"),
  timelineFilterForm: document.getElementById("timelineFilterForm"),
  memeQuery: document.getElementById("memeQuery"),
  sessionFilter: document.getElementById("sessionFilter"),
  timelineSessionFilter: document.getElementById("timelineSessionFilter"),
  clearSessionKey: document.getElementById("clearSessionKey"),
  clearSessionButton: document.getElementById("clearSessionButton"),
  clearAllButton: document.getElementById("clearAllButton"),
  metricGrid: document.getElementById("metricGrid"),
  configList: document.getElementById("configList"),
  versionBadge: document.getElementById("versionBadge"),
  scopeList: document.getElementById("scopeList"),
  memeList: document.getElementById("memeList"),
  memeMeta: document.getElementById("memeMeta"),
  usageBoard: document.getElementById("usageBoard"),
  recentUsage: document.getElementById("recentUsage"),
  timelineList: document.getElementById("timelineList"),
  timelineMeta: document.getElementById("timelineMeta"),
  commandGrid: document.getElementById("commandGrid"),
  quickActions: document.getElementById("quickActions"),
  sidebarDbState: document.getElementById("sidebarDbState"),
  sidebarDbPath: document.getElementById("sidebarDbPath"),
  navItems: [...document.querySelectorAll(".nav-item")],
  sections: [...document.querySelectorAll(".panel-section")],
};

function text(value) {
  return String(value ?? "");
}

function escapeHtml(value) {
  return text(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function yesNo(value) {
  return value ? "开启" : "关闭";
}

function setNotice(message = "", tone = "info") {
  el.notice.hidden = !message;
  el.notice.textContent = message;
  el.notice.className = `notice ${tone}`;
}

function setBridgeState(message, tone = "idle") {
  el.bridgeState.textContent = message;
  el.bridgeState.dataset.tone = tone;
}

async function withTimeout(promise, timeoutMs, message) {
  let timeoutId = 0;
  const timeout = new Promise((_, reject) => {
    timeoutId = window.setTimeout(() => reject(new Error(message)), timeoutMs);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function normalizeApiResult(result, fallbackMessage) {
  if (result && typeof result === "object") {
    if (result.status === "error") {
      throw new Error(result.message || fallbackMessage);
    }
    if (Object.prototype.hasOwnProperty.call(result, "ok")) {
      if (!result.ok) {
        throw new Error(result.error?.message || result.message || fallbackMessage);
      }
      return result.data || {};
    }
  }
  return result || {};
}

function queryString(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

async function fallbackFetch(method, endpoint, payload = {}) {
  const path = `/astrbot_plugin_funbox/${endpoint}`;
  const init = { method, headers: {} };
  let url = path;
  if (method === "GET") {
    url += queryString(payload);
  } else {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(payload);
  }
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.error?.message || data?.message || `HTTP ${response.status}`);
  }
  return normalizeApiResult(data, "请求失败");
}

async function apiGet(endpoint, params = {}) {
  if (bridge?.apiGet) {
    const result = await withTimeout(
      bridge.apiGet(endpoint, params),
      REQUEST_TIMEOUT_MS,
      "请求 AstrBot 页面桥超时，请刷新面板。"
    );
    return normalizeApiResult(result, "请求失败");
  }
  return await fallbackFetch("GET", endpoint, params);
}

async function apiPost(endpoint, body = {}) {
  if (bridge?.apiPost) {
    const result = await withTimeout(
      bridge.apiPost(endpoint, body),
      REQUEST_TIMEOUT_MS,
      "请求 AstrBot 页面桥超时，请刷新面板。"
    );
    return normalizeApiResult(result, "请求失败");
  }
  return await fallbackFetch("POST", endpoint, body);
}

function switchSection(section) {
  state.activeSection = section;
  const titles = {
    overview: "系统总览",
    memes: "梗档案",
    commands: "指令库",
    usage: "玩法热度",
    timeline: "记忆线",
    maintenance: "数据维护",
  };
  el.sectionTitle.textContent = titles[section] || "FunBox";
  for (const item of el.navItems) {
    item.classList.toggle("active", item.dataset.section === section);
  }
  for (const panel of el.sections) {
    panel.classList.toggle("active", panel.id === section);
  }
  if (section === "memes" && !state.memes.length) {
    loadMemes().catch((error) => setNotice(error.message || "梗档案加载失败", "error"));
  }
  if (section === "usage" && !state.usage) {
    loadUsage().catch((error) => setNotice(error.message || "玩法热度加载失败", "error"));
  }
  if (section === "timeline" && !state.timeline.length) {
    loadTimeline().catch((error) => setNotice(error.message || "记忆线加载失败", "error"));
  }
}

function metricCard({ label, value, hint, tone = "violet" }) {
  return `
    <article class="metric-card ${tone}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(hint)}</small>
    </article>
  `;
}

function configRow(label, value, hint = "") {
  return `
    <div class="config-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${hint ? `<small>${escapeHtml(hint)}</small>` : ""}
    </div>
  `;
}

function renderStatus() {
  const data = state.status || {};
  const database = data.database || {};
  const memory = data.memory || {};
  const config = data.config || {};
  const ready = Boolean(database.ready);

  el.sidebarDbState.textContent = ready ? "SQLite 就绪" : config.enable_meme_database ? "SQLite 未就绪" : "数据库已关闭";
  el.sidebarDbPath.textContent = database.db_path || "暂无路径";
  el.versionBadge.textContent = `v${data.version || "-"}`;
  el.clearAllButton.disabled = !config.dashboard_allow_clear_all;

  el.metricGrid.innerHTML = [
    metricCard({ label: "梗档案", value: text(database.total_memes || 0), hint: "SQLite 已收录", tone: "violet" }),
    metricCard({ label: "会话索引", value: text(database.session_count || 0), hint: "存在梗档案的会话", tone: "blue" }),
    metricCard({ label: "玩法次数", value: text(database.total_plays || 0), hint: "已记录的 FunBox 触发", tone: "rose" }),
    metricCard({ label: "记忆事件", value: text(database.total_meme_events || 0), hint: "梗诞生、回收、删除", tone: "blue" }),
    metricCard({ label: "近期样本", value: text(memory.recent_messages || 0), hint: `${memory.sessions || 0} 个会话在内存`, tone: "violet" }),
    metricCard({ label: "数据库", value: ready ? "就绪" : "未就绪", hint: formatBytes(database.db_size_bytes), tone: ready ? "green" : "amber" }),
  ].join("");

  el.configList.innerHTML = [
    configRow("自然语言回复", yesNo(config.enable_natural_reply), config.only_when_addressed ? "仅叫到 bot 时触发" : "明显趣味请求也会触发"),
    configRow("LLM 上下文生成", yesNo(config.enable_llm), "沿用 AstrBot 当前人格"),
    configRow("群聊天气", yesNo(config.enable_group_weather), `LLM 润色 ${yesNo(config.weather_use_llm)}`),
    configRow("群聊榜单", yesNo(config.enable_leaderboard), "抽象王、梗王、问号王"),
    configRow("空间侦探", yesNo(config.enable_space_detective), "说说文案安全锐评"),
    configRow("自动日报", yesNo(config.enable_auto_daily), "到点后群里首次发言触发"),
    configRow("梗档案数据库", yesNo(config.enable_meme_database), `每会话上限 ${config.max_meme_entries || 0}`),
    configRow("面板查询", `${config.dashboard_page_limit || 120} 条`, config.dashboard_allow_clear_all ? "允许面板清空全部" : "默认禁止清空全部"),
    configRow("玩法热度统计", yesNo(config.enable_usage_stats), `记忆线 ${config.dashboard_timeline_limit || 80} 条`),
  ].join("");

  const sessions = Array.isArray(database.sessions) ? database.sessions : [];
  if (!sessions.length) {
    el.scopeList.innerHTML = `
      <div class="empty-state">
        <strong>还没有会话索引</strong>
        <span>在群里用 /梗诞生 登记一句话后，这里会出现会话。</span>
      </div>
    `;
  } else {
    el.scopeList.innerHTML = sessions.map((item) => `
      <button class="scope-chip" type="button" data-session="${escapeHtml(item.session_key)}">
        <span>${escapeHtml(item.session_key)}</span>
        <strong>${escapeHtml(item.count)}</strong>
      </button>
    `).join("");
  }
}

function renderMemes() {
  const total = state.memes.length;
  const database = state.status?.database || {};
  el.memeMeta.textContent = total
    ? `已加载 ${total} 条，数据库共 ${database.total_memes || total} 条`
    : "暂无梗档案";

  if (!total) {
    el.memeList.innerHTML = `
      <div class="empty-state tall">
        <strong>梗库还是空的</strong>
        <span>先在群里发：/梗诞生 这服务器像猫一样不听话</span>
      </div>
    `;
    return;
  }

  el.memeList.innerHTML = state.memes.map((item) => `
    <article class="meme-card" data-id="${escapeHtml(item.id)}">
      <div class="meme-head">
        <div>
          <span class="meme-id">#${escapeHtml(item.id)}</span>
          <h3>${escapeHtml(item.name || "未命名梗")}</h3>
        </div>
        <div class="meme-actions">
          <button class="tiny-button copy-meme" type="button" data-copy="/梗回收 ${escapeHtml(item.name || "")}">复制回收</button>
          <button class="tiny-button danger-text delete-meme" type="button" data-id="${escapeHtml(item.id)}">删除</button>
        </div>
      </div>
      <p class="origin">${escapeHtml(item.origin || "无来源记录")}</p>
      <dl class="meme-detail">
        <div><dt>解释</dt><dd>${escapeHtml(item.meaning || "-")}</dd></div>
        <div><dt>用法</dt><dd>${escapeHtml(item.usage || "-")}</dd></div>
        <div><dt>创建者</dt><dd>${escapeHtml(item.created_by || item.created_by_id || "-")}</dd></div>
        <div><dt>会话</dt><dd>${escapeHtml(item.session_key || "-")}</dd></div>
        <div><dt>回收</dt><dd>${escapeHtml(item.use_count || 0)} 次</dd></div>
        <div><dt>更新</dt><dd>${escapeHtml(item.updated_at || item.created_at || "-")}</dd></div>
      </dl>
    </article>
  `).join("");
}

function eventTypeLabel(value) {
  const labels = {
    birth: "诞生",
    recall: "回收",
    delete: "删除",
  };
  return labels[value] || value || "事件";
}

function renderUsage() {
  const usage = state.usage || { total_plays: 0, top_commands: [], recent: [] };
  const top = Array.isArray(usage.top_commands) ? usage.top_commands : [];
  const recent = Array.isArray(usage.recent) ? usage.recent : [];

  if (!top.length) {
    el.usageBoard.innerHTML = `
      <div class="empty-state tall">
        <strong>玩法热度还没开始升温</strong>
        <span>群里触发几次 FunBox 后，这里会出现排行。</span>
      </div>
    `;
  } else {
    el.usageBoard.innerHTML = `
      <div class="board-title">
        <strong>总触发 ${escapeHtml(usage.total_plays || 0)} 次</strong>
        <span>按玩法累计排行</span>
      </div>
      ${top.map((item, index) => `
        <div class="usage-row">
          <span class="rank">${index + 1}</span>
          <div>
            <strong>${escapeHtml(item.command_key)}</strong>
            <small>最近使用：${escapeHtml(item.last_used || "-")}</small>
          </div>
          <b>${escapeHtml(item.count)} 次</b>
        </div>
      `).join("")}
    `;
  }

  if (!recent.length) {
    el.recentUsage.innerHTML = `
      <div class="empty-state tall">
        <strong>暂无最近触发</strong>
        <span>自然语言触发和斜杠命令都会被记录。</span>
      </div>
    `;
    return;
  }

  el.recentUsage.innerHTML = `
    <div class="board-title">
      <strong>最近触发</strong>
      <span>用于排查哪些玩法真的有人用</span>
    </div>
    ${recent.map((item) => `
      <div class="recent-row">
        <strong>${escapeHtml(item.command_key)}</strong>
        <span>${escapeHtml(item.sender_name || item.sender_id || "-")} · ${escapeHtml(item.created_at || "-")}</span>
        <small>${escapeHtml(item.raw_text || "")}</small>
      </div>
    `).join("")}
  `;
}

function renderTimeline() {
  const items = state.timeline;
  el.timelineMeta.textContent = items.length ? `已加载 ${items.length} 条事件` : "暂无记忆事件";
  if (!items.length) {
    el.timelineList.innerHTML = `
      <div class="empty-state tall">
        <strong>记忆线还是空的</strong>
        <span>登记、回收或删除梗之后，这里会出现时间线。</span>
      </div>
    `;
    return;
  }

  el.timelineList.innerHTML = items.map((item) => `
    <article class="timeline-item ${escapeHtml(item.event_type || "")}">
      <div class="timeline-dot"></div>
      <div class="timeline-body">
        <div class="timeline-head">
          <strong>${escapeHtml(eventTypeLabel(item.event_type))}：${escapeHtml(item.meme_name || "未命名梗")}</strong>
          <span>${escapeHtml(item.created_at || "-")}</span>
        </div>
        <p>${escapeHtml(item.note || "-")}</p>
        <small>${escapeHtml(item.actor_name || item.actor_id || "-")} · ${escapeHtml(item.session_key || "-")}</small>
      </div>
    </article>
  `).join("");
}

function renderCommands() {
  el.commandGrid.innerHTML = commandGroups.map((group) => `
    <article class="command-card">
      <div class="command-title">
        <strong>${escapeHtml(group.title)}</strong>
        <span>${escapeHtml(group.desc)}</span>
      </div>
      <div class="command-list">
        ${group.items.map((item) => `
          <button class="command-pill" type="button" data-copy="${escapeHtml(item)}">${escapeHtml(item)}</button>
        `).join("")}
      </div>
    </article>
  `).join("");

  el.quickActions.innerHTML = quickCommands.map((item) => `
    <button class="quick-button" type="button" data-copy="${escapeHtml(item)}">${escapeHtml(item)}</button>
  `).join("");
}

async function copyText(value) {
  const content = text(value).trim();
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
    setNotice(`已复制：${content}`, "success");
  } catch {
    setNotice(`复制失败，可以手动复制：${content}`, "warn");
  }
}

async function loadStatus() {
  setBridgeState("读取中", "busy");
  const data = await apiGet("page/status");
  state.status = data;
  renderStatus();
  setBridgeState("已连接", "ready");
}

async function loadMemes() {
  state.loading = true;
  el.memeMeta.textContent = "正在加载梗档案";
  const params = {
    q: el.memeQuery.value.trim(),
    session_key: el.sessionFilter.value.trim(),
    limit: state.status?.config?.dashboard_page_limit || 120,
  };
  const data = await apiGet("page/memes", params);
  state.memes = Array.isArray(data.items) ? data.items : [];
  renderMemes();
  state.loading = false;
}

async function loadUsage() {
  const data = await apiGet("page/play-usage", { limit: 18 });
  state.usage = data;
  renderUsage();
}

async function loadTimeline() {
  el.timelineMeta.textContent = "正在加载记忆线";
  const data = await apiGet("page/meme-events", {
    session_key: el.timelineSessionFilter.value.trim(),
    limit: state.status?.config?.dashboard_timeline_limit || 80,
  });
  state.timeline = Array.isArray(data.items) ? data.items : [];
  renderTimeline();
}

async function refreshAll() {
  try {
    await loadStatus();
    if (state.activeSection === "memes") {
      await loadMemes();
    }
    if (state.activeSection === "usage") {
      await loadUsage();
    }
    if (state.activeSection === "timeline") {
      await loadTimeline();
    }
    setNotice("状态已刷新。", "success");
  } catch (error) {
    setBridgeState("连接异常", "error");
    setNotice(error.message || "刷新失败", "error");
  }
}

async function deleteMeme(id) {
  if (!id) return;
  const item = state.memes.find((meme) => String(meme.id) === String(id));
  const label = item?.name ? `「${item.name}」` : `#${id}`;
  if (!window.confirm(`确定删除梗档案 ${label} 吗？`)) return;
  await apiPost("page/delete-meme", { id });
  state.memes = state.memes.filter((meme) => String(meme.id) !== String(id));
  renderMemes();
  await loadStatus();
  if (state.activeSection === "timeline") {
    await loadTimeline();
  }
  setNotice(`已删除 ${label}。`, "success");
}

async function clearMemes(sessionKey) {
  const config = state.status?.config || {};
  const target = text(sessionKey).trim();
  if (!target && !config.dashboard_allow_clear_all) {
    setNotice("当前配置禁止面板清空全部。请填写会话 key，或在插件配置里开启 dashboard_allow_clear_all。", "warn");
    return;
  }
  const message = target
    ? `确定清理会话 ${target} 的梗档案吗？`
    : "确定清空全部梗档案吗？这个操作不可撤销。";
  if (!window.confirm(message)) return;
  if (!target && !window.confirm("再次确认：真的要清空全部梗档案？")) return;
  const data = await apiPost("page/clear-memes", { session_key: target });
  await loadStatus();
  await loadMemes();
  await loadTimeline();
  setNotice(`已清理数据库 ${data.db_removed || 0} 条，内存 ${data.memory_removed || 0} 条。`, "success");
}

function bindEvents() {
  for (const item of el.navItems) {
    item.addEventListener("click", () => switchSection(item.dataset.section));
  }

  el.refreshButton.addEventListener("click", () => refreshAll());
  el.reloadMemesButton.addEventListener("click", () => loadMemes().catch((error) => setNotice(error.message || "加载失败", "error")));
  el.reloadUsageButton.addEventListener("click", () => loadUsage().catch((error) => setNotice(error.message || "加载失败", "error")));
  el.reloadTimelineButton.addEventListener("click", () => loadTimeline().catch((error) => setNotice(error.message || "加载失败", "error")));
  el.loadAllMemesButton.addEventListener("click", async () => {
    el.memeQuery.value = "";
    el.sessionFilter.value = "";
    switchSection("memes");
    await loadMemes();
  });

  el.memeSearchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await loadMemes();
      setNotice("搜索完成。", "success");
    } catch (error) {
      setNotice(error.message || "搜索失败", "error");
    }
  });

  el.timelineFilterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await loadTimeline();
      setNotice("记忆线筛选完成。", "success");
    } catch (error) {
      setNotice(error.message || "筛选失败", "error");
    }
  });

  el.scopeList.addEventListener("click", async (event) => {
    const button = event.target.closest(".scope-chip");
    if (!button) return;
    el.sessionFilter.value = button.dataset.session || "";
    el.timelineSessionFilter.value = button.dataset.session || "";
    switchSection("memes");
    await loadMemes();
  });

  el.memeList.addEventListener("click", async (event) => {
    const copyButton = event.target.closest("[data-copy]");
    if (copyButton) {
      await copyText(copyButton.dataset.copy);
      return;
    }
    const deleteButton = event.target.closest(".delete-meme");
    if (deleteButton) {
      try {
        await deleteMeme(deleteButton.dataset.id);
      } catch (error) {
        setNotice(error.message || "删除失败", "error");
      }
    }
  });

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy]");
    if (!button || el.memeList.contains(button)) return;
    await copyText(button.dataset.copy);
  });

  el.clearSessionButton.addEventListener("click", () => {
    const sessionKey = el.clearSessionKey.value.trim();
    if (!sessionKey) {
      setNotice("清理指定会话需要先填写会话 key。", "warn");
      return;
    }
    clearMemes(sessionKey).catch((error) => setNotice(error.message || "清理失败", "error"));
  });

  el.clearAllButton.addEventListener("click", () => {
    clearMemes("").catch((error) => setNotice(error.message || "清理失败", "error"));
  });
}

async function init() {
  bindEvents();
  renderCommands();
  if (bridge?.ready) {
    try {
      await withTimeout(bridge.ready(), 5000, "页面桥初始化超时");
    } catch (error) {
      setNotice(error.message || "页面桥初始化失败，将尝试直接请求。", "warn");
    }
  }
  try {
    await loadStatus();
    await loadMemes();
    setNotice("FunBox 面板已就绪。", "success");
  } catch (error) {
    setBridgeState("连接异常", "error");
    setNotice(error.message || "面板初始化失败，请确认插件已加载。", "error");
    renderStatus();
    renderMemes();
  }
}

init();
