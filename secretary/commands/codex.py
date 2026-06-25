from __future__ import annotations

from secretary.codex_tui import CodexTuiBridge, CodexTuiError
from secretary.router import CommandSpec


def handle_codex_short(ctx, args: str) -> str:
    return _send_to_codex(ctx, args)


def handle_codex(ctx, args: str) -> str:
    action, _, rest = args.strip().partition(" ")
    action = action.lower()
    if action in ("", "send", "ask"):
        return _send_to_codex(ctx, rest if action else args)
    _require_allowed(ctx)
    if action == "status":
        return _run_bridge(ctx, lambda bridge: bridge.status())
    if action == "capture":
        return _run_bridge(ctx, lambda bridge: bridge.capture())
    if action == "reset":
        return _run_bridge(ctx, lambda bridge: bridge.reset())
    if action in ("interrupt", "stop-current"):
        return _run_bridge(ctx, lambda bridge: bridge.interrupt())
    if action == "stop":
        return _run_bridge(ctx, lambda bridge: bridge.stop())
    return _send_to_codex(ctx, args)


def _send_to_codex(ctx, message: str) -> str:
    _require_allowed(ctx)
    if not message.strip():
        raise ValueError("send a message, for example /c help me think")
    try:
        return _bridge(ctx).send_message_and_capture(_with_bridge_context(ctx, message))
    except CodexTuiError as exc:
        return f"Codex TUI error: {exc}"


def _run_bridge(ctx, action):
    try:
        return action(_bridge(ctx))
    except CodexTuiError as exc:
        return f"Codex TUI error: {exc}"


def _bridge(ctx) -> CodexTuiBridge:
    return CodexTuiBridge(ctx.settings.codex_tui_config)


def _with_bridge_context(ctx, message: str) -> str:
    return (
        "[Feishu secretary bridge] "
        f"owner_id={ctx.owner_id}; "
        "surface=Feishu bot direct message; "
        "role reminder=You are Zhang Shenghao's long-running Codex secretary. "
        "Answer as his secretary, not as a generic fresh Codex session. "
        f"User message: {message.strip()}"
    )


def _require_allowed(ctx) -> None:
    allowed = ctx.settings.allowed_open_ids
    if not allowed:
        raise ValueError(
            "SECRETARY_ALLOWED_OPEN_IDS is not configured. Send /whoami, "
            "then add your open_id to the server .env before enabling Codex control."
        )
    if ctx.owner_id not in allowed:
        raise ValueError(f"open_id {ctx.owner_id} is not allowed to control Codex")


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("c",),
            summary="Send a message to the long-running Codex TUI.",
            usage="/c message",
            handler=handle_codex_short,
        )
    )
    router.register(
        CommandSpec(
            names=("codex",),
            summary="Control the long-running Codex TUI.",
            usage="/codex status|capture|reset|interrupt|stop|message",
            handler=handle_codex,
        )
    )
