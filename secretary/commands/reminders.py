from __future__ import annotations

import re

from secretary.router import CommandSpec
from secretary.timeutils import (
    format_utc,
    parse_datetime_to_utc,
    parse_duration,
    utc_now,
)


_IN_RE = re.compile(r"^in\s+(\d+\s*[smhd])\s+(.+)$", re.IGNORECASE | re.DOTALL)


def handle_remind(ctx, args: str) -> str:
    due_at_utc, message = _parse_remind_args(ctx, args)
    if due_at_utc <= utc_now():
        return "这个提醒时间已经过去了，请给我一个未来时间。"
    due_iso = format_utc(due_at_utc)
    schedule_id = ctx.store.add_schedule(
        owner_id=ctx.owner_id,
        receive_id_type=ctx.receive_id_type,
        receive_id=ctx.receive_id,
        due_at_utc=due_iso,
        message=message,
    )
    return f"已设置提醒 #{schedule_id}\nUTC: {due_iso}\n内容: {message}"


def handle_reminders(ctx, args: str) -> str:
    schedules = ctx.store.list_schedules(ctx.owner_id)
    if not schedules:
        return "目前没有待触发的提醒。"
    lines = ["待触发提醒："]
    for item in schedules:
        lines.append(f"#{item['id']} UTC {item['due_at_utc']} - {item['message']}")
    return "\n".join(lines)


def handle_cancel(ctx, args: str) -> str:
    text = args.strip()
    if not text:
        raise ValueError("请输入提醒编号")
    try:
        schedule_id = int(text)
    except ValueError as exc:
        raise ValueError("提醒编号必须是数字") from exc
    if ctx.store.cancel_schedule(ctx.owner_id, schedule_id):
        return f"已取消提醒 #{schedule_id}。"
    return f"没有找到待取消的提醒 #{schedule_id}。"


def _parse_remind_args(ctx, args: str):
    text = args.strip()
    if not text:
        raise ValueError("请输入时间和提醒内容")

    match = _IN_RE.match(text)
    if match:
        due = utc_now() + parse_duration(match.group(1))
        return due.replace(microsecond=0), match.group(2).strip()

    time_text, sep, message = text.partition(" ")
    if not sep or not message.strip():
        raise ValueError("请输入时间和提醒内容，例如 /remind 2026-06-25T06:30:00Z 开会")
    due = parse_datetime_to_utc(time_text, ctx.settings.default_timezone)
    return due, message.strip()


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("remind", "提醒"),
            summary="设置一个 UTC 日程提醒。",
            usage="/remind 2026-06-25T06:30:00Z 内容",
            handler=handle_remind,
        )
    )
    router.register(
        CommandSpec(
            names=("reminders", "提醒列表"),
            summary="查看还没有触发的提醒。",
            usage="/reminders",
            handler=handle_reminders,
        )
    )
    router.register(
        CommandSpec(
            names=("cancel", "取消提醒"),
            summary="取消一个待触发提醒。",
            usage="/cancel 3",
            handler=handle_cancel,
        )
    )

