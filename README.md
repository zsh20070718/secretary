# Personal Secretary

一个轻量的本地个人秘书服务，通过飞书自建应用接收你的消息，支持 UTC 日程提醒、待办、备忘和资料搜索。

## 特点

- 纯 Python 标准库为主，无运行时依赖，资源占用小。
- 本地 SQLite 存储，默认数据库在 `data/secretary.sqlite3`。
- 所有日程时间都以 UTC ISO 8601 格式保存，例如 `2026-06-25T06:30:00Z`。
- 命令模块自动注册，新增功能只需要在 `secretary/commands/` 下添加一个模块。
- 飞书事件入口支持 URL 验证和 `im.message.receive_v1` 文本消息事件。

## 快速启动

1. 复制配置：

```powershell
Copy-Item .env.example .env
```

2. 编辑 `.env`，填写飞书自建应用信息：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=xxx
```

3. 启动服务：

```powershell
python -m secretary
```

4. 暴露本地端口给飞书访问。开发阶段可以用 ngrok、cloudflared 或内网穿透工具，把公网 HTTPS 地址指向本地 `8080` 端口。

5. 在飞书开放平台配置事件订阅：

- 请求地址：`https://你的公网域名/feishu/events`
- 事件：`im.message.receive_v1`
- 消息权限：给应用开启接收消息、发送消息相关权限，并发布/安装应用。
- 加密策略：当前版本先不要启用事件加密。

## 可用命令

在飞书里给机器人发送：

```text
/help
```

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

## 健康检查

```powershell
curl http://127.0.0.1:8080/health
```

返回 `ok` 表示服务正常。

