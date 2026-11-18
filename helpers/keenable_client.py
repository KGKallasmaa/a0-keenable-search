"""Small async Keenable search client for the Agent Zero keenable_search plugin.

Only depends on aiohttp, so it can be unit tested without an Agent Zero checkout.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import aiohttp

KEYLESS_URL = "https://api.keenable.ai/v1/search/public"
KEYED_URL = "https://api.keenable.ai/v1/search"
TITLE = "Agent Zero"
LIMIT_MESSAGE = (
    "Keenable rate limit reached; use search_engine (SearXNG) "
    "or set KEENABLE_API_KEY."
)


class KeenableError(Exception):
    """Non-rate-limit failure talking to Keenable."""


class KeenableRateLimited(KeenableError):
    """HTTP 429 from Keenable."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass
class SearchResponse:
    results: list[SearchResult] = field(default_factory=list)
    keyed: bool = False


def build_request(query: str, count: int, api_key: str | None) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Return (url, json body, headers) for a keyless or keyed search."""
    body = {"query": query, "max_results": int(count)}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
        return KEYED_URL, body, headers
    headers["X-Keenable-Title"] = TITLE
    return KEYLESS_URL, body, headers


def parse_results(data: Any, limit: int) -> list[SearchResult]:
    """Map results[] (title, url, snippet, description) to SearchResult."""
    out: list[SearchResult] = []
    for item in (data or {}).get("results") or []:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        snippet = (item.get("snippet") or item.get("description") or "").strip()
        out.append(SearchResult(title=(item.get("title") or "").strip(), url=item["url"], snippet=snippet))
        if len(out) >= limit:
            break
    return out


def format_results(results: list[SearchResult]) -> str:
    """Same plain-text shape as Agent Zero's search_engine: title\\nurl\\nsnippet blocks."""
    return "\n\n".join(f"{r.title}\n{r.url}\n{r.snippet}" for r in results).strip()


async def search(
    query: str,
    *,
    count: int = 10,
    api_key: str | None = None,
    timeout: float = 15,
    session: aiohttp.ClientSession | None = None,
) -> SearchResponse:
    url, body, headers = build_request(query, count, api_key)
    own = session is None
    sess = session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))
    try:
        # Never follow redirects: aiohttp would resend X-API-Key to the new host.
        async with sess.post(url, json=body, headers=headers, allow_redirects=False) as resp:
            if resp.status == 429:
                raise KeenableRateLimited(LIMIT_MESSAGE)
            if 300 <= resp.status < 400:
                raise KeenableError(f"Keenable search failed: unexpected redirect (HTTP {resp.status})")
            if resp.status >= 400:
                # Status only: the raw API error body stays out of the chat history.
                raise KeenableError(f"Keenable search failed: HTTP {resp.status}")
            data = await resp.json(content_type=None)
    except aiohttp.ClientError as e:
        raise KeenableError(f"Keenable search failed: {type(e).__name__}") from e
    finally:
        if own:
            await sess.close()
    return SearchResponse(results=parse_results(data, count), keyed=bool(api_key))
