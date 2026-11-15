import os
import types

import pytest

from conftest import client, tool, plugins_mod, secrets_mod

SAMPLE = {"results": [
    {"url": "https://a.example", "title": "A", "snippet": "snip a", "description": ""},
    {"url": "https://b.example", "title": "B", "description": "desc b"},
    {"title": "no url"},
]}


class _Resp:
    def __init__(self, status, payload, body):
        self.status, self._payload, self._body = status, payload, body

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class MockHTTP:
    """Patches aiohttp.ClientSession in the client module and records POSTs."""

    def __init__(self, status=200, payload=None, body=""):
        self.status, self.payload, self.body = status, payload, body
        self.calls = []

    def __enter__(self):
        harness = self

        class FakeSession:
            def __init__(self, *a, **k):
                pass

            def post(self, url, json=None, headers=None):
                harness.calls.append(types.SimpleNamespace(url=url, json=json, headers=headers))
                return _Resp(harness.status, harness.payload, harness.body)

            async def close(self):
                pass

        self._orig = client.aiohttp.ClientSession
        client.aiohttp.ClientSession = FakeSession
        return self

    def __exit__(self, *a):
        client.aiohttp.ClientSession = self._orig
        return False


class Agent:
    def __init__(self):
        self.context = None
        self.interventions = []

    async def handle_intervention(self, msg):
        self.interventions.append(msg)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    plugins_mod.CONFIG = {}
    secrets_mod.SECRETS = {}
    monkeypatch.delenv("KEENABLE_API_KEY", raising=False)


def test_parse_and_format():
    res = client.parse_results(SAMPLE, 10)
    assert [r.url for r in res] == ["https://a.example", "https://b.example"]
    assert res[0].snippet == "snip a"
    assert res[1].snippet == "desc b"
    assert client.format_results(res) == "A\nhttps://a.example\nsnip a\n\nB\nhttps://b.example\ndesc b"
    assert len(client.parse_results(SAMPLE, 1)) == 1
    assert client.parse_results({}, 5) == []


def test_build_request():
    url, body, headers = client.build_request("q", 5, None)
    assert url == "https://api.keenable.ai/v1/search/public"
    assert body == {"query": "q", "max_results": 5}
    assert headers["X-Keenable-Title"] == "Agent Zero" and "X-API-Key" not in headers
    url, _, headers = client.build_request("q", 5, "k")
    assert url == "https://api.keenable.ai/v1/search"
    assert headers["X-API-Key"] == "k" and "X-Keenable-Title" not in headers


@pytest.mark.asyncio
async def test_tool_keyless():
    agent = Agent()
    with MockHTTP(payload=SAMPLE) as http:
        res = await tool.KeenableSearch(agent=agent).execute(query="hello")
    assert http.calls[0].url == client.KEYLESS_URL
    assert http.calls[0].json == {"query": "hello", "max_results": 10}
    assert res.message.startswith("A\nhttps://a.example")
    assert agent.interventions == [res.message]


@pytest.mark.asyncio
async def test_key_from_config_then_secrets_then_env(monkeypatch):
    plugins_mod.CONFIG = {"api_key": "cfg-key", "results": 3}
    secrets_mod.SECRETS = {"KEENABLE_API_KEY": "secret-key"}
    monkeypatch.setenv("KEENABLE_API_KEY", "env-key")
    with MockHTTP(payload=SAMPLE) as http:
        await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert http.calls[0].url == client.KEYED_URL
    assert http.calls[0].headers["X-API-Key"] == "cfg-key"
    assert http.calls[0].json["max_results"] == 3

    plugins_mod.CONFIG = {}
    with MockHTTP(payload=SAMPLE) as http:
        await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert http.calls[0].headers["X-API-Key"] == "secret-key"

    secrets_mod.SECRETS = {}
    with MockHTTP(payload=SAMPLE) as http:
        await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert http.calls[0].headers["X-API-Key"] == "env-key"


@pytest.mark.asyncio
async def test_rate_limit_falls_back_to_searxng():
    with MockHTTP(status=429):
        res = await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert client.LIMIT_MESSAGE in res.message
    assert "https://sx.example" in res.message

    plugins_mod.CONFIG = {"fallback_to_searxng": False}
    with MockHTTP(status=429):
        res = await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert res.message == client.LIMIT_MESSAGE


@pytest.mark.asyncio
async def test_http_error_and_empty():
    with MockHTTP(status=500, body="boom"):
        res = await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert res.message == "Keenable search failed: HTTP 500 boom"
    with MockHTTP(payload={"results": []}):
        res = await tool.KeenableSearch(agent=Agent()).execute(query="q")
    assert res.message == "No results from Keenable."
    res = await tool.KeenableSearch(agent=Agent()).execute(query="")
    assert res.message == "Error: no query provided"


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("KEENABLE_LIVE") != "1", reason="set KEENABLE_LIVE=1")
async def test_live_keyless():
    res = await client.search("agent zero framework", count=3)
    assert res.results and all(r.url.startswith("http") for r in res.results)
