from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .feishu import FeishuClient
    from .config import Settings
    from .search import SearchClient
    from .store import Store


Handler = Callable[["CommandContext", str], str]


@dataclass
class CommandContext:
    owner_id: str
    receive_id_type: str
    receive_id: str
    raw_text: str
    store: "Store"
    settings: "Settings"
    search_client: "SearchClient"
    feishu: "FeishuClient | None" = None
    router: "Router | None" = None


@dataclass(frozen=True)
class CommandSpec:
    names: tuple[str, ...]
    summary: str
    usage: str
    handler: Handler

    @property
    def primary_name(self) -> str:
        return self.names[0]


class Router:
    def __init__(self):
        self._commands: dict[str, CommandSpec] = {}
        self._ordered: list[CommandSpec] = []

    def register(self, command: CommandSpec) -> None:
        if not command.names:
            raise ValueError("command must have at least one name")
        self._ordered.append(command)
        for name in command.names:
            self._commands[self._normalize_name(name)] = command

    def dispatch(self, ctx: CommandContext, text: str) -> str:
        clean = text.strip()
        ctx.router = self
        if not clean:
            return self.unknown_message()
        first, _, args = clean.partition(" ")
        name = self._normalize_name(first)
        command = self._commands.get(name)
        if command is None:
            return self.unknown_message()
        try:
            return command.handler(ctx, args.strip())
        except ValueError as exc:
            return f"参数不对：{exc}\n\n用法：{command.usage}"

    def format_help(self) -> str:
        lines = ["可用命令："]
        seen: set[str] = set()
        for command in self._ordered:
            if command.primary_name in seen:
                continue
            seen.add(command.primary_name)
            lines.append(f"{command.usage}\n  {command.summary}")
        return "\n".join(lines)

    @staticmethod
    def unknown_message() -> str:
        return "我还不认识这句。发送 /help 查看可用命令。"

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.strip().lstrip("/").lower()
