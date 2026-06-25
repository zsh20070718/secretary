# Personal Secretary

一个轻量的本地个人秘书服务。默认用飞书长连接模式运行：你的笔记本主动连接飞书开放平台，因此不需要公网域名，也不需要把本机端口暴露到公网。

## 当前能力

- 飞书长连接收消息，适合本机常驻运行。
- 保留 webhook 模式，未来有公网 HTTPS 地址时可切换。
- UTC 日程提醒，支持绝对时间和 `in 10m` 这类相对时间。
- 本地 SQLite 存储待办、备忘和提醒。
- 资料搜索，默认 DuckDuckGo Instant Answer，可配置 Bing Search API。
- 命令模块自动注册，新增功能只需要在 `secretary/commands/` 下添加文件。

## 安装

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`：

```env
SECRETARY_FEISHU_EVENT_MODE=long_connection
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=xxx
```

启动：

```powershell
python -m secretary
```

启动后保持这个终端开着。你在飞书里给机器人发消息，本机进程会通过长连接收到事件并回复。

## 飞书后台配置

你需要在飞书开放平台创建一个企业自建应用，并完成这些配置：

- 应用能力：开启机器人。
- 事件订阅：选择“使用长连接接收事件”，订阅 `im.message.receive_v1`。
- 权限：开启接收消息、以机器人身份发送消息相关权限。
- 发布/安装：把应用发布并安装到你的企业或个人测试租户。
- 可用范围：确保机器人对你本人或目标群可见。

配置完成后，在飞书里给机器人发送：

```text
/help
```

如果本机终端正在运行，秘书应该回复可用命令列表。

## 可用命令

Codex TUI：

```text
/whoami
/c 帮我想一下这个项目下一步怎么做
/codex status
/codex capture
/codex interrupt
/codex reset
/codex stop
```

`/c` 和 `/codex` 会控制服务器上的长期 Codex TUI。为了安全，必须先配置：

```env
SECRETARY_ALLOWED_OPEN_IDS=你的 open_id
CODEX_TUI_COMMAND=codex
CODEX_TUI_WORKDIR=/srv/secretary/codex-workspace
CODEX_TUI_TMUX_SESSION=secretary-codex
```

如果不知道自己的 `open_id`，先给机器人发送 `/whoami`。

日程提醒：

```text
/remind 2026-06-25T06:30:00Z 开会
/remind 2026-06-25T14:30:00+08:00 开会
/remind in 10m 喝水
/reminders
/cancel 3
```

待办：

```text
/todo add 写项目 README
/todo list
/todo done 1
```

备忘：

```text
/note add 护照放在抽屉
/note list
```

资料搜索：

```text
/search Python sqlite WAL mode
```

## Webhook 备用模式

如果以后你有公网 HTTPS 地址，或者想用 ngrok/cloudflared 做临时调试，可以切到 webhook：

```env
SECRETARY_FEISHU_EVENT_MODE=webhook
SECRETARY_HOST=0.0.0.0
SECRETARY_PORT=8080
```

然后在飞书事件订阅里配置：

```text
https://你的公网地址/feishu/events
```

当前 webhook 模式不支持事件加密；如需使用加密事件，后续可以加。

## 服务器上跑长期 Codex

Linux 服务器需要有 `tmux` 和 Codex CLI。推荐用单独用户运行秘书，不要用 root。最小启动方式：

```bash
cd /srv/secretary
python3 -m pip install -r requirements.txt
python3 -m secretary
```

秘书会在第一次收到 `/c ...` 时自动创建 tmux session，并在其中启动 Codex TUI。也可以手动查看：

```bash
tmux attach -t secretary-codex
```

公网只需要飞书能连接到你的 bot；Codex TUI 不需要、也不应该暴露任何公网端口。

## 扩展新功能

在 `secretary/commands/` 下新增一个文件，例如 `weather.py`：

```python
from secretary.router import CommandSpec


def handle_weather(ctx, args):
    city = args.strip() or "Shanghai"
    return f"Weather command placeholder: {city}"


def register(router):
    router.register(CommandSpec(
        names=("weather",),
        summary="查询天气",
        usage="/weather Shanghai",
        handler=handle_weather,
    ))
```

重启服务后，`/weather Shanghai` 就会自动可用。

## 时间规则

- 存储和展示默认使用 UTC：`YYYY-MM-DDTHH:MM:SSZ`。
- 推荐输入带时区的 ISO 8601 时间，例如 `2026-06-25T14:30:00+08:00`。
- 如果输入没有时区，例如 `2026-06-25T14:30:00`，会按 `SECRETARY_DEFAULT_TIMEZONE` 解释，再转换为 UTC。

## 本地健康检查

健康检查只在 webhook 模式下开启：

```powershell
curl http://127.0.0.1:8080/health
```

返回 `ok` 表示 HTTP 服务正常。
