from __future__ import annotations

from secretary.router import CommandSpec


def handle_note(ctx, args: str) -> str:
    action, _, rest = args.strip().partition(" ")
    action = action.lower()
    rest = rest.strip()

    if action in ("add", "new", "记"):
        if not rest:
            raise ValueError("请输入备忘内容")
        note_id = ctx.store.add_note(ctx.owner_id, rest)
        return f"已记录备忘 #{note_id}。"

    if action in ("list", "ls", ""):
        notes = ctx.store.list_notes(ctx.owner_id)
        if not notes:
            return "目前没有备忘。"
        lines = ["最近备忘："]
        for note in notes:
            lines.append(f"#{note['id']} [{note['created_at_utc']}] {note['content']}")
        return "\n".join(lines)

    raise ValueError("支持 add/list，例如 /note add 护照放在抽屉")


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("note", "memo", "备忘"),
            summary="新增或查看备忘。",
            usage="/note add 内容 | /note list",
            handler=handle_note,
        )
    )

