# AstrBot FunBox

安全轻量的群聊趣味工具箱。它会缓存最近群聊上下文，并优先使用 AstrBot 当前 LLM provider 生成趣味回复；LLM 不可用时自动退回规则模板。

## 功能

- `/趣味帮助`
- `/今日人设`
- `/赛博塔罗`
- `/氛围雷达`
- `/名场面`
- `/今日运势`
- `/抽象指数 [内容]`
- `/群聊热词`

也可以直接叫 bot 昵称自然触发，例如：

```text
机器人昵称，群里现在什么氛围？
机器人昵称，刚刚有什么名场面？
机器人昵称，我今天运势咋样？
```

## 配置项

- `enable_natural_reply`: 是否启用自然语言回复。
- `only_when_addressed`: 是否仅在叫到 bot 名字时自然回复，默认开启，避免乱插嘴。
- `extra_trigger_names`: 额外触发名，例如 `小雪`、`赛博盒子`。
- `max_cache_messages`: 每个会话缓存消息数，默认 90。
- `enable_llm`: 是否启用 LLM 上下文生成，关闭后只使用内置模板。

## 安装

把插件目录放到 AstrBot 插件目录：

```bash
data/plugins/astrbot_plugin_funbox
```

然后重载插件或重启 AstrBot。

## 说明

- 每个会话最多缓存 90 条最近消息。
- 不额外依赖数据库。
- 不配置 LLM 也能使用兜底模板。
