import json

import pytest
from httpx import ASGITransport, AsyncClient

from main import DATA, app, find_by_id, load_json, mcp, search_items


def parse_sse_json(text: str) -> dict:
    """Parse SSE response and extract JSON from data lines."""
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


@pytest.fixture(autouse=True)
def _load_data():
    """Load test data before each test."""
    DATA["best_practices"] = load_json("best_practices.json")
    DATA["snippets"] = load_json("snippets.json")
    DATA["troubleshooting"] = load_json("troubleshooting.json")
    DATA["tips"] = load_json("tips.json")
    DATA["governance"] = load_json("governance.json")
    yield
    DATA.clear()


@pytest.fixture
def api_key_headers():
    return {"X-API-Key": "mcs-bootcamp-2025"}


@pytest.fixture
def mcp_headers():
    return {
        "X-API-Key": "mcs-bootcamp-2025",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


@pytest.fixture
async def mcp_client():
    """Client with fresh MCP ASGI app lifespan (session manager is single-use)."""
    fresh_mcp_app = mcp.http_app(path="/", stateless_http=True)
    from starlette.routing import Mount

    original_routes = list(app.routes)
    app.routes[:] = [r for r in app.routes if not (isinstance(r, Mount) and r.path == "/mcp")]
    app.routes.append(Mount("/mcp", app=fresh_mcp_app))

    ctx = fresh_mcp_app.lifespan(fresh_mcp_app)
    await ctx.__aenter__()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
            yield c
    finally:
        try:
            await ctx.__aexit__(None, None, None)
        except RuntimeError:
            pass  # anyio cancel scope teardown across tasks — harmless
        app.routes[:] = original_routes


# ---------------------------------------------------------------------------
# Unit tests: search_items
# ---------------------------------------------------------------------------


class TestSearchItems:
    def test_empty_query_returns_first_10(self):
        items = [{"title": f"Item {i}"} for i in range(15)]
        result = search_items(items, "", ["title"])
        assert len(result) == 10

    def test_search_matches_string_field(self):
        items = [
            {"title": "Handle errors gracefully", "id": "1"},
            {"title": "Use variables", "id": "2"},
        ]
        result = search_items(items, "error", ["title"])
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_search_matches_list_field(self):
        items = [
            {"title": "Item A", "tags": ["http", "api"]},
            {"title": "Item B", "tags": ["testing"]},
        ]
        result = search_items(items, "http", ["tags"])
        assert len(result) == 1
        assert result[0]["title"] == "Item A"

    def test_search_case_insensitive(self):
        items = [{"title": "HTTP Connector"}]
        result = search_items(items, "http", ["title"])
        assert len(result) == 1

    def test_search_scoring_ranks_multiple_matches_higher(self):
        items = [
            {"title": "Error handling", "description": "Handle errors"},
            {"title": "Variables", "description": "Use variables"},
        ]
        result = search_items(items, "error", ["title", "description"])
        assert result[0]["title"] == "Error handling"

    def test_no_matches_returns_empty(self):
        items = [{"title": "Something"}]
        result = search_items(items, "nonexistent", ["title"])
        assert len(result) == 0


class TestFindById:
    def test_finds_existing(self):
        items = [{"id": "bp-001", "title": "Test"}]
        assert find_by_id(items, "bp-001")["title"] == "Test"

    def test_returns_none_for_missing(self):
        items = [{"id": "bp-001"}]
        assert find_by_id(items, "bp-999") is None


# ---------------------------------------------------------------------------
# REST API tests
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_no_auth(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_health_with_auth_also_works(self, client, api_key_headers):
        resp = await client.get("/health", headers=api_key_headers)
        assert resp.status_code == 200


class TestAuth:
    async def test_no_key_returns_401(self, client):
        resp = await client.get("/api/v1/best-practices")
        assert resp.status_code == 401

    async def test_wrong_key_returns_401(self, client):
        resp = await client.get("/api/v1/best-practices", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    async def test_valid_key_passes(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices", headers=api_key_headers)
        assert resp.status_code == 200


class TestBestPractices:
    async def test_list_all(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices", headers=api_key_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) <= 10

    async def test_search(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices?q=error", headers=api_key_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0

    async def test_filter_category(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices?category=security", headers=api_key_headers)
        data = resp.json()
        for item in data["results"]:
            assert item["category"] == "security"

    async def test_filter_difficulty(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices?difficulty=beginner", headers=api_key_headers)
        data = resp.json()
        for item in data["results"]:
            assert item["difficulty"] == "beginner"

    async def test_get_by_id(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices/bp-001", headers=api_key_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == "bp-001"

    async def test_get_by_id_not_found(self, client, api_key_headers):
        resp = await client.get("/api/v1/best-practices/bp-999", headers=api_key_headers)
        assert resp.status_code == 404


class TestSnippets:
    async def test_list_all(self, client, api_key_headers):
        resp = await client.get("/api/v1/snippets", headers=api_key_headers)
        assert resp.status_code == 200

    async def test_filter_language(self, client, api_key_headers):
        resp = await client.get("/api/v1/snippets?language=power-fx", headers=api_key_headers)
        data = resp.json()
        for item in data["results"]:
            assert item["language"] == "power-fx"

    async def test_search(self, client, api_key_headers):
        resp = await client.get("/api/v1/snippets?q=email", headers=api_key_headers)
        data = resp.json()
        assert len(data["results"]) > 0

    async def test_get_by_id(self, client, api_key_headers):
        resp = await client.get("/api/v1/snippets/snip-001", headers=api_key_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == "snip-001"


class TestTroubleshooting:
    async def test_list_all(self, client, api_key_headers):
        resp = await client.get("/api/v1/troubleshooting", headers=api_key_headers)
        assert resp.status_code == 200

    async def test_search(self, client, api_key_headers):
        resp = await client.get("/api/v1/troubleshooting?q=403", headers=api_key_headers)
        data = resp.json()
        assert len(data["results"]) > 0

    async def test_get_by_id(self, client, api_key_headers):
        resp = await client.get("/api/v1/troubleshooting/ts-001", headers=api_key_headers)
        assert resp.status_code == 200


class TestTips:
    async def test_list_all(self, client, api_key_headers):
        resp = await client.get("/api/v1/tips", headers=api_key_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 10

    async def test_filter_category(self, client, api_key_headers):
        resp = await client.get("/api/v1/tips?category=testing", headers=api_key_headers)
        data = resp.json()
        for item in data["results"]:
            assert item["category"] == "testing"


class TestGovernance:
    async def test_get_feature(self, client, api_key_headers):
        resp = await client.get("/api/v1/governance/http-connector", headers=api_key_headers)
        assert resp.status_code == 200
        assert resp.json()["feature"] == "http-connector"

    async def test_get_feature_fuzzy(self, client, api_key_headers):
        resp = await client.get("/api/v1/governance/mcp", headers=api_key_headers)
        assert resp.status_code == 200
        assert "mcp" in resp.json()["feature"]

    async def test_not_found(self, client, api_key_headers):
        resp = await client.get("/api/v1/governance/nonexistent-feature", headers=api_key_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# MCP endpoint tests
# ---------------------------------------------------------------------------


class TestMCPEndpoint:
    async def test_mcp_requires_auth(self, mcp_client):
        resp = await mcp_client.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert resp.status_code == 401

    async def test_mcp_initialize(self, mcp_client, mcp_headers):
        resp = await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert resp.status_code == 200
        data = parse_sse_json(resp.text)
        assert data.get("jsonrpc") == "2.0"
        result = data.get("result", {})
        assert "serverInfo" in result
        assert "capabilities" in result

    async def test_mcp_tools_list(self, mcp_client, mcp_headers):
        # Initialize first
        await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        # Send initialized notification
        await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        # List tools
        resp = await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}},
        )
        assert resp.status_code == 200
        data = parse_sse_json(resp.text)
        tools = data.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert "search_best_practices" in tool_names
        assert "get_code_snippet" in tool_names
        assert "troubleshoot_issue" in tool_names
        assert "get_tips_for_feature" in tool_names
        assert "check_governance_zone" in tool_names
        assert len(tools) == 5

    async def test_mcp_tool_call(self, mcp_client, mcp_headers):
        # Initialize
        await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        # Call tool
        resp = await mcp_client.post(
            "/mcp",
            headers=mcp_headers,
            json={
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tools/call",
                "params": {"name": "search_best_practices", "arguments": {"query": "error"}},
            },
        )
        assert resp.status_code == 200
        data = parse_sse_json(resp.text)
        content = data.get("result", {}).get("content", [])
        assert len(content) > 0
        assert content[0]["type"] == "text"
        assert "error" in content[0]["text"].lower()
