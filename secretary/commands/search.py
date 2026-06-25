from __future__ import annotations

from secretary.router import CommandSpec


def handle_search(ctx, args: str) -> str:
    query = args.strip()
    if not query:
        raise ValueError("请输入搜索关键词")
    try:
        results = ctx.search_client.search(query)
    except Exception as exc:
        return f"搜索失败：{exc}"

    if not results:
        return "没有找到可靠结果。可以配置 BING_SEARCH_API_KEY 获得更完整的网页搜索。"

    lines = [f"搜索结果：{query}"]
    for index, item in enumerate(results, start=1):
        snippet = item.snippet.strip()
        if len(snippet) > 180:
            snippet = f"{snippet[:177]}..."
        lines.append(f"{index}. {item.title}\n{item.url}\n{snippet}")
    return "\n\n".join(lines)


def register(router) -> None:
    router.register(
        CommandSpec(
            names=("search", "查找", "搜索"),
            summary="搜索资料并把结果发回飞书。",
            usage="/search 关键词",
            handler=handle_search,
        )
    )

