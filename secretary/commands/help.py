from __future__ import annotations

from secretary.router import CommandSpec


def handle_help(ctx, args: str) -> str:
    if ctx.router is None:
        return "帮助暂不可用。"
    return ctx.router.format_help()


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("help", "h", "帮助"),
            summary="查看秘书能处理的命令。",
            usage="/help",
            handler=handle_help,
        )
    )

