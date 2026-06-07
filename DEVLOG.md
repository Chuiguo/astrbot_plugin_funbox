# FunBox 开发日志

## 2026-06-07 - v1.4.0 群聊速写

### 改动内容
- 新增 `/群聊速写`。
- 新增别名：`/速写`、`/群聊快照`、`/聊天快照`。
- 新增自然语言意图 `snapshot`，可由 `速写`、`群聊速写`、`快照`、`聊天快照`、`群聊切片`、`刚刚聊了啥` 等触发。
- 在 `main.py` 新增 `_build_group_snapshot(event)`。
- 同步更新菜单、示例、推荐逻辑、自然语言兜底、面板命令列表、README 和 metadata。
- 版本号更新到 `1.4.0` / `v1.4.0`。

### 行为说明
- 使用当前会话内存里的最近群聊样本。
- 至少需要 4 条最近文本样本。
- 会统计热词、参与人数、候选名场面、笑点/问号/感叹号等信号。
- 优先通过 `_generate_with_context` 调 LLM 生成。
- LLM 不可用时有确定性兜底文案。
- 最近群聊样本不写数据库。

### 验证记录
- `main.py` AST 语法检查通过。
- `pages/dashboard/app.js` 通过 `node --check`。
- 本地打包为 `funbox-v1.4.0.tar.gz`，已排除 `__pycache__` 和 `.pyc`。

### GitHub 记录
- 仓库：`https://github.com/Chuiguo/astrbot_plugin_funbox.git`
- 本轮使用分支：`codex/funbox-v0.5.0`
- 功能提交：`6ab0749 Add group snapshot command`

### 服务器更新命令
如果服务器插件目录已经是 Git 仓库：

```bash
cd ~/astrbot/data/plugins/astrbot_plugin_funbox
git fetch origin
git checkout codex/funbox-v0.5.0
git pull origin codex/funbox-v0.5.0
docker restart astrbot
```

如果服务器插件目录不是 Git 仓库：

```bash
cd ~/astrbot/data/plugins
mv astrbot_plugin_funbox astrbot_plugin_funbox.bak.$(date +%Y%m%d%H%M%S)
git clone -b codex/funbox-v0.5.0 https://github.com/Chuiguo/astrbot_plugin_funbox.git astrbot_plugin_funbox
docker restart astrbot
```

### 重启后冒烟测试
```text
/funbox自检
/群聊速写
盒子，刚刚群里聊了啥？
/趣味菜单 群聊
```

### 下次接手注意
- 改 FunBox 时同步更新这个文件。
- 不要只依赖聊天上下文记录部署状态。
- 不要在这里记录 API key、代理订阅链接、cookie 或其他密钥。
- 工作区可能有其他脏文件，只 stage FunBox 仓库里本次需要提交的文件。

## 2026-06-07 - 增加更新说明

### 改动内容
- 新增 `UPDATE_GUIDE.md`。
- 记录常规 GitHub 更新流程。
- 记录 mihomo 代理更新流程，包括当前服务器观测到的 `7898` mixed 代理端口。
- 记录重启后的测试命令和常见故障排查。

### GitHub 记录
- 文档提交：`5119f59 Add server update guide`

## 2026-06-07 - 文档中文化

### 改动内容
- 将 `UPDATE_GUIDE.md` 从英文改为中文。
- 将 `DEVLOG.md` 从英文改为中文。
- 保留命令、分支、提交号等关键信息。

## 2026-06-07 - 精品路线约定

### 版本策略
- 大目标定为 `v2.0 精品版 FunBox`。
- 不一次性堆大功能，先用 `v1.4.x` 小版本逐步打磨。
- 每个小版本只解决一个明确体验问题，方便测试、回滚和复盘。

### 打磨原则
- 少加新功能，多提升已有功能质量。
- 菜单和帮助文案保持克制，不把入口越堆越满。
- 输出要短、有画面、有记忆点，避免流水账。
- 每次修改同步写中文开发日志。

### 近期路线
- `v1.4.1`：群聊速写精品化，只打磨 `/群聊速写`。
- `v1.4.2`：精简菜单和帮助文案。
- `v1.4.3`：优化自然语言触发体验。
- `v1.4.4`：整理稳定性和兜底回复。
- `v2.0.0`：完成一轮精品化后再发布大版本标记。

## 2026-06-07 - v1.4.1 群聊速写精品化

### 改动目标
- 不新增玩法，只打磨 `/群聊速写`。
- 让速写更像群聊切片，不像总结报告。
- 样本不足时不再说“启动失败”，改成自然等待提示。

### 改动内容
- 版本号更新到 `1.4.1` / `v1.4.1`。
- `/群聊速写` 输出收敛为固定四行：标题、画面、镜头、旁白。
- LLM prompt 明确要求不列统计、不写日报、不单独列关键词。
- 增加输出清洗：LLM 偶尔多说解释时，只保留速写四行；格式不合格则回退 fallback。
- fallback 文案改成更有画面的短切片。
- 菜单、示例、推荐理由同步改成更克制的描述。

## 2026-06-07 - v1.4.2 菜单和帮助精简

### 改动目标
- 不删功能，只减少默认展示压力。
- `/趣味菜单` 从完整命令墙改成精选入口。
- `/funbox示例` 从 12 条压到 6 条。

### 改动内容
- 版本号更新到 `1.4.2` / `v1.4.2`。
- 新增 `MENU_OVERVIEW`，默认菜单只展示精选、群聊、梗档案、个人、维护五行入口。
- 分类帮助仍保留完整命令：例如 `/趣味帮助 群聊`、`/趣味帮助 梗档案`。
- metadata、README、管理面板快捷命令同步精简。
