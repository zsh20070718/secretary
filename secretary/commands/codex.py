from __future__ import annotations

import threading

from secretary.codex_tui import CodexTuiBridge, CodexTuiError
from secretary.logging_utils import get_logger
from secretary.router import CommandSpec


logger = get_logger(__name__)
WORKING_REPLY = "\u6b63\u5728\u505a"
_CODEX_TASK_LOCK = threading.Lock()


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
    if not _CODEX_TASK_LOCK.acquire(blocking=False):
        return WORKING_REPLY
    if ctx.feishu is None:
        try:
            return _bridge(ctx).send_message_and_capture(_with_bridge_context(ctx, message))
        finally:
            _CODEX_TASK_LOCK.release()

    thread = threading.Thread(
        target=_send_to_codex_worker,
        args=(ctx, message),
        name="codex-tui-worker",
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        _CODEX_TASK_LOCK.release()
        raise
    return WORKING_REPLY


def _send_to_codex_worker(ctx, message: str) -> None:
    try:
        reply = _bridge(ctx).send_message_and_capture(_with_bridge_context(ctx, message))
    except CodexTuiError as exc:
        reply = f"Codex TUI error: {exc}"
    except Exception as exc:
        logger.exception("Unexpected Codex worker failure: %s", exc)
        reply = f"Codex worker error: {exc}"
    try:
        ctx.feishu.send_text(ctx.receive_id_type, ctx.receive_id, reply)
    except Exception as exc:
        logger.exception("Failed to send Codex worker reply: %s", exc)
    finally:
        _CODEX_TASK_LOCK.release()


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
