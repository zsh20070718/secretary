from __future__ import annotations

from secretary.router import CommandSpec


def handle_whoami(ctx, args: str) -> str:
    return (
        f"owner_id: {ctx.owner_id}\n"
        f"receive_id_type: {ctx.receive_id_type}\n"
        f"receive_id: {ctx.receive_id}"
    )


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("whoami",),
            summary="Show your Feishu IDs for access control setup.",
            usage="/whoami",
            handler=handle_whoami,
        )
    )

