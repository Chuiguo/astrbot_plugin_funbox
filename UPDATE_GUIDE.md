# FunBox Update Guide

This guide records the repeatable deployment steps for updating FunBox on the AstrBot server.

## Current Repository

- GitHub: `https://github.com/Chuiguo/astrbot_plugin_funbox.git`
- Branch used by the current server workflow: `codex/funbox-v0.5.0`
- Plugin path on server: `~/astrbot/data/plugins/astrbot_plugin_funbox`

## Normal Update

Run on the server:

```bash
cd ~/astrbot/data/plugins/astrbot_plugin_funbox

git fetch origin
git checkout codex/funbox-v0.5.0
git pull origin codex/funbox-v0.5.0

git log -2 --oneline
docker restart astrbot
```

After a successful update for the v1.4.0 snapshot work, `git log -2 --oneline` should include:

```text
35832e5 Add FunBox development log
6ab0749 Add group snapshot command
```

## Update Through Mihomo Proxy

If direct GitHub access fails with errors like `Failed to connect to github.com port 443`, use mihomo.

Check the actual listening port:

```bash
systemctl status mihomo -l --no-pager
ss -lntp | grep mihomo
```

Example from the current server:

```text
Mixed(http+socks) proxy listening at: [::]:7898
LISTEN ... [::]:7898 ... users:(("mihomo",...))
```

In that case, test GitHub through port `7898`:

```bash
curl -x http://127.0.0.1:7898 -I https://github.com --connect-timeout 15
```

Then update through the proxy:

```bash
cd ~/astrbot/data/plugins/astrbot_plugin_funbox

git -c http.proxy=http://127.0.0.1:7898 \
    -c https.proxy=http://127.0.0.1:7898 \
    fetch origin

git checkout codex/funbox-v0.5.0

git -c http.proxy=http://127.0.0.1:7898 \
    -c https.proxy=http://127.0.0.1:7898 \
    pull origin codex/funbox-v0.5.0

git log -2 --oneline
docker restart astrbot
```

## If The Plugin Directory Is Not A Git Clone

Back up the existing plugin directory, then clone the repo:

```bash
cd ~/astrbot/data/plugins

mv astrbot_plugin_funbox astrbot_plugin_funbox.bak.$(date +%Y%m%d%H%M%S)

git clone -b codex/funbox-v0.5.0 https://github.com/Chuiguo/astrbot_plugin_funbox.git astrbot_plugin_funbox

docker restart astrbot
```

If GitHub direct access fails, clone through the proxy:

```bash
cd ~/astrbot/data/plugins

mv astrbot_plugin_funbox astrbot_plugin_funbox.bak.$(date +%Y%m%d%H%M%S)

git -c http.proxy=http://127.0.0.1:7898 \
    -c https.proxy=http://127.0.0.1:7898 \
    clone -b codex/funbox-v0.5.0 https://github.com/Chuiguo/astrbot_plugin_funbox.git astrbot_plugin_funbox

docker restart astrbot
```

## Smoke Tests

Send these in chat after restarting AstrBot:

```text
/funbox自检
/群聊速写
盒子，刚刚群里聊了啥？
/趣味菜单 群聊
```

## Troubleshooting

### `curl: (7) Failed to connect to 127.0.0.1 port 7897`

The proxy is not listening on `7897`. Check the actual port:

```bash
ss -lntp | grep mihomo
```

Use the `Mixed(http+socks)` port reported by mihomo, for example `7898`.

### `Already on 'codex/funbox-v0.5.0'` but code is still old

This usually means `fetch` failed, so Git only checked the old local branch. Run:

```bash
git log -2 --oneline
```

If it does not show the expected new commit, repeat the proxy update steps above.

### Restart succeeded but command does not exist

Check that AstrBot is loading the same plugin directory:

```bash
docker logs --tail 200 astrbot | grep -i funbox
```

Then verify the plugin code on the server:

```bash
grep -n "群聊速写" ~/astrbot/data/plugins/astrbot_plugin_funbox/main.py
```
