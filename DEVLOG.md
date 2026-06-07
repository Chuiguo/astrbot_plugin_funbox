# FunBox Development Log

## 2026-06-07 - v1.4.0 group snapshot

### What changed
- Added `/群聊速写`.
- Added aliases: `/速写`, `/群聊快照`, `/聊天快照`.
- Added natural language intent `snapshot`, triggered by phrases such as `速写`, `群聊速写`, `快照`, `聊天快照`, `群聊切片`, `刚刚聊了啥`.
- Added `_build_group_snapshot(event)` in `main.py`.
- Updated menu text, examples, recommendation logic, natural fallbacks, dashboard command list, README, and metadata.
- Bumped version references to `1.4.0` / `v1.4.0`.

### Behavior
- Uses recent in-memory group samples.
- Requires at least 4 recent text samples.
- Builds hot words, speaker count, candidate scenes, laugh/question/exclaim signals.
- Uses LLM through `_generate_with_context`.
- Has a deterministic fallback if LLM is unavailable.
- Does not write recent group samples to database.

### Validation
- `main.py` AST parse passed.
- `pages/dashboard/app.js` syntax check passed with `node --check`.
- Packaged locally as `funbox-v1.4.0.tar.gz`, excluding `__pycache__` and `.pyc`.

### GitHub
- Repo: `https://github.com/Chuiguo/astrbot_plugin_funbox.git`
- Branch used this session: `codex/funbox-v0.5.0`
- Commit pushed: `6ab0749 Add group snapshot command`

### Server update commands
If the server plugin directory is already a git clone:

```bash
cd ~/astrbot/data/plugins/astrbot_plugin_funbox
git fetch origin
git checkout codex/funbox-v0.5.0
git pull origin codex/funbox-v0.5.0
docker restart astrbot
```

If the server plugin directory is not a git clone:

```bash
cd ~/astrbot/data/plugins
mv astrbot_plugin_funbox astrbot_plugin_funbox.bak.$(date +%Y%m%d%H%M%S)
git clone -b codex/funbox-v0.5.0 https://github.com/Chuiguo/astrbot_plugin_funbox.git astrbot_plugin_funbox
docker restart astrbot
```

### Smoke tests after restart
```text
/funbox自检
/群聊速写
盒子，刚刚群里聊了啥？
/趣味菜单 群聊
```

### Notes for next session
- Keep this file updated while changing FunBox.
- Do not rely only on chat context for deployment state.
- Do not record API keys, proxy subscription URLs, cookies, or other secrets here.
- The workspace can contain unrelated dirty files; only stage intended FunBox repo changes.
