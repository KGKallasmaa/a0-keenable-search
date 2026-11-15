# Keenable Search for Agent Zero

Adds a `keenable_search` tool next to Agent Zero's built-in SearXNG `search_engine`. SearXNG stays the default; the agent only uses this tool when `search_engine` comes up empty or you ask for Keenable

I work with Keenable

## How it works

- No key: `POST https://api.keenable.ai/v1/search/public` with an `X-Keenable-Title: Agent Zero` header. Limits without a key are 1,000 requests/hour and 10/sec per IP
- With a key (plugin settings, or `KEENABLE_API_KEY` in Agent Zero secrets / env): `POST https://api.keenable.ai/v1/search` with `X-API-Key`. Keys come with 100k free requests a month
- On HTTP 429 it says so and falls back to SearXNG (can be turned off)

Results use the same `title\nurl\nsnippet` text shape as `search_engine`

## Install

Install from the Agent Zero plugin index, or clone this repo into `usr/plugins/keenable_search`

## Settings

| Key | Default | |
|---|---|---|
| `api_key` | `""` | optional, falls back to `KEENABLE_API_KEY` |
| `results` | `10` | max results |
| `timeout` | `15` | seconds |
| `fallback_to_searxng` | `true` | use SearXNG on a rate limit |

## Tests

```
pip install -r dev/requirements-dev.txt
cd dev && pytest
KEENABLE_LIVE=1 pytest -m live   # hits the real keyless endpoint
```

Layout follows [brainsparker/a0-youcom-search](https://github.com/brainsparker/a0-youcom-search) (MIT). Keenable docs: https://docs.keenable.ai
