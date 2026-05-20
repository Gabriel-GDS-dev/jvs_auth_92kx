from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import quote_plus

import requests


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class HybridSearch:
    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        results: list[SearchResult] = []
        results.extend(self._duckduckgo(query, limit))
        if os.getenv("SEARXNG_URL"):
            results.extend(self._searxng(query, limit))
        return self._rank(results, limit)

    def _duckduckgo(self, query: str, limit: int) -> list[SearchResult]:
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                return [
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("href", ""),
                        snippet=item.get("body", ""),
                    )
                    for item in ddgs.text(query, max_results=limit)
                ]
        except Exception:
            return []

    def _searxng(self, query: str, limit: int) -> list[SearchResult]:
        try:
            url = os.getenv("SEARXNG_URL", "").rstrip("/")
            response = requests.get(
                f"{url}/search",
                params={"q": query, "format": "json"},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            return [
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
                for item in data.get("results", [])[:limit]
            ]
        except Exception:
            return []

    def smart_scrape(self, url: str, limit_chars: int = 8000) -> str:
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "Jarvis/1.0"})
            response.raise_for_status()
            html = response.text
            html = re.sub(r"(?is)<(script|style|nav|footer|header|aside).*?</\\1>", " ", html)
            text = re.sub(r"(?s)<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", unescape(text)).strip()
            return text[:limit_chars]
        except Exception as exc:
            return f"Erro ao extrair {url}: {exc}"

    def _rank(self, results: list[SearchResult], limit: int) -> list[SearchResult]:
        seen = set()
        weighted = []
        for item in results:
            if not item.url or item.url in seen:
                continue
            seen.add(item.url)
            score = 0
            lower = item.url.lower()
            if any(domain in lower for domain in (".gov", ".edu", "wikipedia", "github", "python.org", ".br")):
                score += 2
            if any(bad in lower for bad in ("ads", "doubleclick", "tracking")):
                score -= 5
            weighted.append((score, item))
        weighted.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in weighted[:limit]]

