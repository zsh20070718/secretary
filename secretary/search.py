from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import Settings


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if self.settings.bing_search_api_key:
            return self._bing(query, limit)
        return self._duckduckgo(query, limit)

    def _bing(self, query: str, limit: int) -> list[SearchResult]:
        params = urllib.parse.urlencode({"q": query, "count": limit, "mkt": "zh-CN"})
        request = urllib.request.Request(
            f"{self.settings.bing_search_endpoint}?{params}",
            headers={"Ocp-Apim-Subscription-Key": self.settings.bing_search_api_key},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
        values = data.get("webPages", {}).get("value", [])
        return [
            SearchResult(
                title=item.get("name", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
            )
            for item in values[:limit]
        ]

    def _duckduckgo(self, query: str, limit: int) -> list[SearchResult]:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
                "skip_disambig": "1",
            }
        )
        request = urllib.request.Request(
            f"https://api.duckduckgo.com/?{params}",
            headers={"User-Agent": "personal-secretary/0.1"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))

        results: list[SearchResult] = []
        abstract = data.get("AbstractText") or ""
        abstract_url = data.get("AbstractURL") or ""
        heading = data.get("Heading") or query
        if abstract and abstract_url:
            results.append(SearchResult(heading, abstract_url, abstract))

        self._collect_related(data.get("RelatedTopics", []), results, limit)
        return results[:limit]

    def _collect_related(
        self,
        topics: list[dict[str, Any]],
        results: list[SearchResult],
        limit: int,
    ) -> None:
        for item in topics:
            if len(results) >= limit:
                return
            if "Topics" in item:
                self._collect_related(item.get("Topics", []), results, limit)
                continue
            text = item.get("Text") or ""
            url = item.get("FirstURL") or ""
            if text and url:
                title = text.split(" - ", 1)[0][:80]
                results.append(SearchResult(title=title, url=url, snippet=text))

