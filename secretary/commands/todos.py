from __future__ import annotations

from secretary.router import CommandSpec


def handle_todo(ctx, args: str) -> str:
    action, _, rest = args.strip().partition(" ")
    action = action.lower()
    rest = rest.strip()

    if action in ("add", "new", "新增"):
        if not rest:
            raise ValueError("请输入待办内容")
        todo_id = ctx.store.add_todo(ctx.owner_id, rest)
        return f"已新增待办 #{todo_id}：{rest}"

    if action in ("list", "ls", ""):
        include_done = rest.lower() in ("all", "done")
        todos = ctx.store.list_todos(ctx.owner_id, include_done=include_done)
        if not todos:
            return "目前没有待办。"
        lines = ["待办列表："]
        for todo in todos:
            marker = "x" if todo["status"] == "done" else " "
            lines.append(f"[{marker}] #{todo['id']} {todo['title']}")
        return "\n".join(lines)

    if action in ("done", "finish", "完成"):
        if not rest:
            raise ValueError("请输入待办编号")
        try:
            todo_id = int(rest)
        except ValueError as exc:
            raise ValueError("待办编号必须是数字") from exc
        if ctx.store.finish_todo(ctx.owner_id, todo_id):
            return f"已完成待办 #{todo_id}。"
        return f"没有找到未完成待办 #{todo_id}。"

    raise ValueError("支持 add/list/done，例如 /todo add 写 README")


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("todo", "待办"),
            summary="维护个人待办列表。",
            usage="/todo add 内容 | /todo list | /todo done 1",
            handler=handle_todo,
        )
    )

