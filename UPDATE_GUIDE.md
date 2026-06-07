# FunBox 更新说明

这份文档记录 FunBox 在 AstrBot 服务器上的固定更新流程。后续更新插件时，优先照这里操作，避免只靠聊天记录找命令。

## 当前仓库信息

- GitHub：`https://github.com/Chuiguo/astrbot_plugin_funbox.git`
- 当前使用分支：`codex/funbox-v0.5.0`
- 服务器插件路径：`~/astrbot/data/plugins/astrbot_plugin_funbox`

## 常规更新

在服务器执行：

```bash
cd ~/astrbot/data/plugins/astrbot_plugin_funbox

git fetch origin
git checkout codex/funbox-v0.5.0
git pull origin codex/funbox-v0.5.0

git log -3 --oneline
docker restart astrbot
```

本次 `v1.4.0` 更新成功后，`git log -3 --oneline` 应该能看到类似：

```text
5119f59 Add server update guide
35832e5 Add FunBox development log
6ab0749 Add group snapshot command
```

## GitHub 连不上时走 mihomo 代理

如果出现下面这种错误：

```text
Failed to connect to github.com port 443
```

说明服务器直连 GitHub 失败，需要让 Git 走 mihomo。

先查看 mihomo 实际监听端口：

```bash
systemctl status mihomo -l --no-pager
ss -lntp | grep mihomo
```

当前服务器上看到的是：

```text
Mixed(http+socks) proxy listening at: [::]:7898
LISTEN ... [::]:7898 ... users:(("mihomo",...))
```

所以本机代理端口是 `7898`，不是 `7897`。

先测试代理能不能访问 GitHub：

```bash
curl -x http://127.0.0.1:7898 -I https://github.com --connect-timeout 15
```

如果能连通，再执行代理更新：

```bash
cd ~/astrbot/data/plugins/astrbot_plugin_funbox

git -c http.proxy=http://127.0.0.1:7898 \
    -c https.proxy=http://127.0.0.1:7898 \
    fetch origin

git checkout codex/funbox-v0.5.0

git -c http.proxy=http://127.0.0.1:7898 \
    -c https.proxy=http://127.0.0.1:7898 \
    pull origin codex/funbox-v0.5.0

git log -3 --oneline
docker restart astrbot
```

## 插件目录不是 Git 仓库时

如果服务器上的 `astrbot_plugin_funbox` 不是 Git 仓库，先备份旧目录，再重新克隆：

```bash
cd ~/astrbot/data/plugins

mv astrbot_plugin_funbox astrbot_plugin_funbox.bak.$(date +%Y%m%d%H%M%S)

git clone -b codex/funbox-v0.5.0 https://github.com/Chuiguo/astrbot_plugin_funbox.git astrbot_plugin_funbox

docker restart astrbot
```

如果直连 GitHub 失败，就用代理克隆：

```bash
cd ~/astrbot/data/plugins

mv astrbot_plugin_funbox astrbot_plugin_funbox.bak.$(date +%Y%m%d%H%M%S)

git -c http.proxy=http://127.0.0.1:7898 \
    -c https.proxy=http://127.0.0.1:7898 \
    clone -b codex/funbox-v0.5.0 https://github.com/Chuiguo/astrbot_plugin_funbox.git astrbot_plugin_funbox

docker restart astrbot
```

## 重启后测试

AstrBot 重启后，在聊天里发送：

```text
/funbox自检
/群聊速写
盒子，刚刚群里聊了啥？
/趣味菜单 群聊
```

## 常见问题

### `127.0.0.1:7897` 连不上

说明代理没有监听 `7897`。先查真实端口：

```bash
ss -lntp | grep mihomo
```

以 mihomo 日志里的 `Mixed(http+socks)` 端口为准。当前服务器实际是 `7898`。

### 显示已经在分支上，但代码还是旧的

如果看到：

```text
Already on 'codex/funbox-v0.5.0'
Your branch is up to date
```

但 `git log` 还是旧提交，通常是 `fetch` 没成功，Git 只是基于旧的本地缓存判断“已最新”。

检查：

```bash
git log -3 --oneline
```

如果没有看到新提交，就按“GitHub 连不上时走 mihomo 代理”重新拉取。

### 重启成功但命令不存在

先确认 AstrBot 加载的是同一个插件目录：

```bash
docker logs --tail 200 astrbot | grep -i funbox
```

再确认服务器代码里有新命令：

```bash
grep -n "群聊速写" ~/astrbot/data/plugins/astrbot_plugin_funbox/main.py
```

如果 grep 没结果，说明服务器还没拉到新版代码。
