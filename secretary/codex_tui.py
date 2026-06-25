from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import time
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path

from .logging_utils import get_logger


logger = get_logger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PROMPT_MARK = "\u203a"
_CODEX_STATUS_RE = re.compile(r"^\s*gpt-[\w.\- ]+\s*[\u00b7/].*$", re.IGNORECASE)
_PERSONA_BEGIN = "<!-- secretary-persona:begin -->"
_PERSONA_END = "<!-- secretary-persona:end -->"
DEFAULT_PERSONA = f"""{_PERSONA_BEGIN}
# Personal Secretary Codex Persona

You are the user's long-running Codex secretary, not a fresh generic coding
assistant. You live in a persistent Codex TUI session on the user's server and
are reached through a Feishu bot bridge.

## Identity

- Your owner is Zhang Shenghao. Treat messages as coming from him through
  Feishu unless the bridge explicitly says otherwise.
- Your role is a capable personal secretary with Codex-level engineering
  ability: think clearly, remember project context through files, help plan,
  maintain tasks, inspect code, edit code, run tests, and explain tradeoffs.
- Default to Chinese when the user writes Chinese, English when the user writes
  English, and a natural mix when the user mixes both.
- Be warm, concise, and operational. The user wants a useful long-term working
  partner, not a generic bot or a verbose help page.

## Operating Model

- Feishu is the remote chat surface. Your replies may be forwarded back through
  Feishu, so keep first replies compact and high-signal.
- This is a persistent TUI session. Use files in this workspace for durable
  memory. Prefer creating or updating small markdown files when the user asks
  you to remember stable preferences, plans, or project context.
- Do not claim to remember facts that are not in the current session or saved
  files. If memory matters, save it explicitly.
- When the user asks for broad help, identify the next concrete step and move
  toward it. When the request is risky or ambiguous, ask a short clarifying
  question.

## Engineering Behavior

- Before changing code, inspect the relevant files and follow the existing
  project style.
- Keep changes scoped. Do not do unrelated refactors.
- Run tests or targeted verification when practical, and tell the user what
  passed or what could not be run.
- Never intentionally expose secrets. Do not print API keys, app secrets,
  tokens, or full environment dumps.
- Do not run destructive commands unless the user clearly requested them and
  the target is understood.

## Secretary Behavior

- Help maintain reminders, todos, notes, project plans, and lightweight
  decisions. If something should persist beyond the chat, write it to a file
  the user can inspect.
- Surface status clearly: what you saw, what you changed, what remains.
- If a task will take time, send a short status-oriented reply first, then
  continue working in the session.

## Bridge Context

- Messages may arrive prefixed with metadata such as Feishu owner_id. Use that
  metadata only for context and access control awareness; respond to the
  user's actual message.
- If the current screen appears to show stale input or partial terminal state,
  ask the user to use `/codex capture`, `/codex interrupt`, or `/codex reset`
  rather than pretending the task completed.
{_PERSONA_END}
"""


class CodexTuiError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodexTuiConfig:
    command: str
    workdir: Path
    session: str
    capture_lines: int
    response_timeout_seconds: int
    stable_seconds: int
    max_reply_chars: int


class CodexTuiBridge:
    def __init__(self, config: CodexTuiConfig):
        self.config = config

    def ensure_session(self) -> None:
        if self.session_exists():
            return
        self._require_tmux()
        self.config.workdir.mkdir(parents=True, exist_ok=True)
        self.ensure_persona_file()
        shell_command = self.config.command
        logger.info(
            "Starting Codex TUI session=%s workdir=%s command=%s",
            self.config.session,
            self.config.workdir,
            self.config.command,
        )
        command_args = shlex.split(shell_command)
        self._run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                self.config.session,
                "-c",
                str(self.config.workdir),
                *command_args,
            ],
            check=True,
        )
        time.sleep(1.5)

    def session_exists(self) -> bool:
        self._require_tmux()
        result = self._run(
            ["tmux", "has-session", "-t", self.config.session],
            check=False,
        )
        return result.returncode == 0

    def send_message_and_capture(self, message: str) -> str:
        text = message.strip()
        if not text:
            raise ValueError("missing Codex message")

        self.ensure_session()
        before = self.capture()
        self._paste(text)
        after = self._wait_for_response(before, text)
        if not after:
            after = self.capture()
        delta = extract_delta_capture(before, after, submitted_text=text)
        return self._format_capture(delta)

    def ensure_persona_file(self) -> None:
        path = self.config.workdir / "AGENTS.md"
        if not path.exists():
            path.write_text(DEFAULT_PERSONA + "\n", encoding="utf-8")
            return

        existing = path.read_text(encoding="utf-8")
        if _PERSONA_BEGIN in existing and _PERSONA_END in existing:
            start = existing.index(_PERSONA_BEGIN)
            end = existing.index(_PERSONA_END) + len(_PERSONA_END)
            updated = existing[:start] + DEFAULT_PERSONA + existing[end:]
        else:
            separator = "\n\n" if existing.strip() else ""
            updated = existing.rstrip() + separator + DEFAULT_PERSONA + "\n"
        if updated != existing:
            path.write_text(updated, encoding="utf-8")

    def capture(self) -> str:
        if not self.session_exists():
            raise CodexTuiError("Codex TUI session is not running.")
        result = self._run(
            [
                "tmux",
                "capture-pane",
                "-p",
                "-J",
                "-S",
                f"-{self.config.capture_lines}",
                "-t",
                self.config.session,
            ],
            check=True,
            text=True,
        )
        return clean_terminal_text(result.stdout)

    def status(self) -> str:
        if not self.session_exists():
            return "Codex TUI is stopped."
        return (
            f"Codex TUI is running.\n"
            f"session: {self.config.session}\n"
            f"workdir: {self.config.workdir}"
        )

    def interrupt(self) -> str:
        if not self.session_exists():
            return "Codex TUI is already stopped."
        self._run(["tmux", "send-keys", "-t", self.config.session, "C-c"], check=True)
        return "Sent Ctrl-C to Codex TUI."

    def reset(self) -> str:
        if self.session_exists():
            self.stop()
        self.ensure_session()
        return "Restarted Codex TUI."

    def stop(self) -> str:
        if not self.session_exists():
            return "Codex TUI is already stopped."
        self._run(["tmux", "kill-session", "-t", self.config.session], check=True)
        return "Stopped Codex TUI."

    def _paste(self, text: str) -> None:
        literal = text.replace("\r\n", "\n").replace("\r", "\n")
        literal = " / ".join(part.strip() for part in literal.splitlines() if part.strip())
        self._run(
            ["tmux", "send-keys", "-t", self.config.session, "-l", literal],
            check=True,
        )
        time.sleep(0.5)
        self._run(["tmux", "send-keys", "-t", self.config.session, "Enter"], check=True)

    def _wait_for_response(self, before: str, submitted_text: str) -> str:
        deadline = time.monotonic() + self.config.response_timeout_seconds
        stable_since: float | None = None
        last = before
        changed = ""
        response = ""
        while time.monotonic() < deadline:
            time.sleep(1)
            current = self.capture()
            if current != last:
                changed = current
                last = current
                if extract_delta_capture(before, current, submitted_text=submitted_text):
                    response = current
                    stable_since = time.monotonic()
                else:
                    stable_since = None
                continue
            if response and stable_since is not None:
                if time.monotonic() - stable_since >= self.config.stable_seconds:
                    return response
        return response or changed

    def _format_capture(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return "Codex TUI has no visible output yet. Try /codex capture."
        if len(cleaned) <= self.config.max_reply_chars:
            return cleaned
        head = cleaned[-self.config.max_reply_chars :]
        return f"... output truncated ...\n{head}"

    @staticmethod
    def _require_tmux() -> None:
        if shutil.which("tmux") is None:
            raise CodexTuiError("tmux is not installed or not in PATH.")

    @staticmethod
    def _run(
        args: list[str],
        *,
        input_data: bytes | None = None,
        check: bool,
        text: bool = False,
    ) -> subprocess.CompletedProcess:
        logger.debug("Running command: %s", " ".join(shlex.quote(arg) for arg in args))
        try:
            result = subprocess.run(
                args,
                input=input_data,
                capture_output=True,
                text=text,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CodexTuiError(f"Command not found: {args[0]}") from exc
        if check and result.returncode != 0:
            stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode(
                "utf-8",
                errors="replace",
            )
            raise CodexTuiError(stderr.strip() or f"Command failed: {args[0]}")
        return result


def clean_terminal_text(text: str) -> str:
    without_ansi = _ANSI_RE.sub("", text)
    without_controls = _CONTROL_RE.sub("", without_ansi)
    lines = [line.rstrip() for line in without_controls.splitlines()]
    return "\n".join(lines).strip()


def extract_delta_capture(
    before: str,
    after: str,
    *,
    submitted_text: str | None = None,
) -> str:
    before_clean = clean_terminal_text(before)
    after_clean = clean_terminal_text(after)
    if not after_clean or before_clean == after_clean:
        return ""

    before_lines = before_clean.splitlines()
    after_lines = after_clean.splitlines()
    start = _find_delta_start(before_lines, after_lines)
    delta_lines = after_lines[start:] if start is not None else after_lines
    cleaned = _trim_delta_lines(delta_lines, submitted_text=submitted_text)
    if cleaned:
        return "\n".join(cleaned).strip()
    if start is None:
        return after_clean
    return ""


def _find_delta_start(before_lines: list[str], after_lines: list[str]) -> int | None:
    if not before_lines:
        return 0

    matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    best: tuple[int, int, int] | None = None
    for block in matcher.get_matching_blocks():
        if block.size == 0:
            continue
        block_lines = after_lines[block.b : block.b + block.size]
        useful_lines = [line for line in block_lines if not _is_tui_chrome_line(line)]
        useful_chars = sum(len(line.strip()) for line in useful_lines)
        if not useful_lines:
            continue
        score = (block.a + block.size, block.b + block.size, useful_chars)
        if best is None or score > best:
            best = score

    if best is None:
        return None
    return best[1]


def _trim_delta_lines(lines: list[str], *, submitted_text: str | None) -> list[str]:
    trimmed = list(lines)

    while trimmed and not trimmed[0].strip():
        trimmed.pop(0)
    while trimmed and _is_prompt_echo_line(trimmed[0], submitted_text):
        trimmed.pop(0)
        while trimmed and not trimmed[0].strip():
            trimmed.pop(0)

    while trimmed and (
        not trimmed[-1].strip()
        or _is_tui_chrome_line(trimmed[-1])
        or _is_trailing_prompt_line(trimmed[-1])
    ):
        trimmed.pop()

    return trimmed


def _is_prompt_echo_line(line: str, submitted_text: str | None) -> bool:
    stripped = line.strip()
    if not stripped.startswith(_PROMPT_MARK):
        return False
    if "[Feishu secretary bridge]" in stripped or "User message:" in stripped:
        return True
    if submitted_text:
        return _compact(submitted_text)[:80] in _compact(stripped)
    return True


def _is_trailing_prompt_line(line: str) -> bool:
    stripped = line.strip()
    return stripped == ">" or stripped.startswith(_PROMPT_MARK)


def _is_tui_chrome_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(_PROMPT_MARK):
        return True
    if _CODEX_STATUS_RE.match(line):
        return True
    if stripped.startswith(("gpt-", "model:", "directory:", "Tip:")):
        return True
    return False


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
