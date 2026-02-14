import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from loguru import logger

load_dotenv()

logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="{time:DD-MM-YYYY at HH:mm:ss} | {level: <8} | {message}",
)

API_KEYS = set(key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip())
DATA_DIR = Path(__file__).parent / "data"
DATA: dict[str, list] = {}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_json(filename: str) -> list | dict:
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    logger.warning(f"Data file not found: {filepath}")
    return []


# ---------------------------------------------------------------------------
# Search helper
# ---------------------------------------------------------------------------


def search_items(items: list, query: str, fields: list[str]) -> list:
    if not query:
        return items[:10]
    query_lower = query.lower()
    results = []
    for item in items:
        score = 0
        for field in fields:
            value = item.get(field, "")
            if isinstance(value, str) and query_lower in value.lower():
                score += 1
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, str) and query_lower in v.lower():
                        score += 1
        if score > 0:
            results.append((score, item))
    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:10]]


def find_by_id(items: list, item_id: str) -> dict | None:
    for item in items:
        if item.get("id") == item_id:
            return item
    return None


# ---------------------------------------------------------------------------
# Format helpers (for MCP resources — full detail)
# ---------------------------------------------------------------------------


def format_best_practice_full(item: dict) -> str:
    lines = [
        f"# {item['title']}",
        f"\n**Category**: {item.get('category', 'N/A')}",
        f"**Difficulty**: {item.get('difficulty', 'N/A')}",
        f"\n**Description**: {item['description']}",
        f"\n**Rationale**: {item.get('rationale', '')}",
        f"\n**Good example**: {item.get('example_good', '')}",
        f"**Bad example**: {item.get('example_bad', '')}",
        f"\n**Tags**: {', '.join(item.get('tags', []))}",
    ]
    return "\n".join(lines)


def format_snippet_full(item: dict) -> str:
    lines = [
        f"# {item['title']}",
        f"\n**Language**: {item.get('language', 'unknown')}",
        f"**Use case**: {item.get('use_case', '')}",
        f"\n```{item.get('language', '')}\n{item.get('code', '')}\n```",
        f"\n**Explanation**: {item.get('explanation', '')}",
        f"\n**Tags**: {', '.join(item.get('tags', []))}",
    ]
    return "\n".join(lines)


def format_troubleshooting_full(item: dict) -> str:
    lines = [f"# {item['title']}"]
    if item.get("symptoms"):
        lines.append("\n**Symptoms**:")
        for s in item["symptoms"]:
            lines.append(f"- {s}")
    if item.get("causes"):
        lines.append("\n**Possible causes**:")
        for c in item["causes"]:
            lines.append(f"- {c}")
    if item.get("steps"):
        lines.append("\n**Resolution steps**:")
        for step in item["steps"]:
            lines.append(f"\n**Step {step['step']}**: {step['action']}")
            lines.append(f"  {step['details']}")
    return "\n".join(lines)


def format_tip_full(item: dict) -> str:
    lines = [
        f"# {item['title']}",
        f"\n{item.get('tip', '')}",
    ]
    if item.get("why_it_matters"):
        lines.append(f"\n*Why it matters*: {item['why_it_matters']}")
    lines.append(f"\n**Tags**: {', '.join(item.get('tags', []))}")
    return "\n".join(lines)


def format_governance_full(item: dict) -> str:
    lines = [
        f"# {item.get('display_name', item.get('feature'))}",
        f"\n**Minimum zone required**: {item.get('minimum_zone', 'unknown')}",
        "\n**Availability by zone**:",
    ]
    for zone, info in item.get("zones", {}).items():
        available = "Available" if info.get("available") else "Not available"
        lines.append(f"\n**{zone.upper()}**: {available}")
        if info.get("reason"):
            lines.append(f"  Reason: {info['reason']}")
        if info.get("requirements"):
            lines.append(f"  Requirements: {', '.join(info['requirements'])}")
    if item.get("justification_template"):
        lines.append(f"\n**Justification template**:\n> {item['justification_template']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FastAPI app (lifespan composed with MCP app lifespan)
# ---------------------------------------------------------------------------

# MCP server defined later, but we need a forward reference for the ASGI app
# to compose lifespans. We'll set it up after MCP tools/resources are registered.
_mcp_asgi_app = None


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    DATA["best_practices"] = load_json("best_practices.json")
    DATA["snippets"] = load_json("snippets.json")
    DATA["troubleshooting"] = load_json("troubleshooting.json")
    DATA["tips"] = load_json("tips.json")
    DATA["governance"] = load_json("governance.json")
    logger.info(
        f"Loaded: {len(DATA['best_practices'])} best practices, "
        f"{len(DATA['snippets'])} snippets, {len(DATA['troubleshooting'])} troubleshooting, "
        f"{len(DATA['tips'])} tips, {len(DATA['governance'])} governance"
    )
    # Run MCP app's lifespan so its session manager task group initializes
    async with _mcp_asgi_app.lifespan(_mcp_asgi_app):
        yield


app = FastAPI(
    title="MCS Best Practices",
    description="Curated Copilot Studio best practices API + MCP server",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def mcp_accept_middleware(request: Request, call_next):
    """Inject Accept header for MCP POST requests if missing — Azure API Hub strips it."""
    if request.url.path.startswith("/mcp") and request.method == "POST":
        accept = request.headers.get("accept", "")
        if "text/event-stream" not in accept:
            headers = dict(request.scope["headers"])
            headers[b"accept"] = b"application/json, text/event-stream"
            request.scope["headers"] = list(headers.items())
    return await call_next(request)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path.startswith("/mcp") and request.method == "GET":
        return JSONResponse({"status": "ok", "server": "MCS Best Practices MCP", "protocol": "mcp-streamable-1.0"})
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key not in API_KEYS:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Health check (no auth — middleware skips /health)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "healthy", "data_loaded": bool(DATA)}


# ---------------------------------------------------------------------------
# REST API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/best-practices")
async def list_best_practices(
    q: str | None = None,
    category: str | None = None,
    difficulty: str | None = None,
):
    items = DATA.get("best_practices", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    if difficulty:
        items = [i for i in items if i.get("difficulty") == difficulty]
    if q:
        items = search_items(items, q, ["title", "description", "tags", "rationale"])
    return {"results": items[:10], "total": len(items)}


@app.get("/api/v1/best-practices/{id}")
async def get_best_practice(id: str):
    item = find_by_id(DATA.get("best_practices", []), id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.get("/api/v1/snippets")
async def list_snippets(q: str | None = None, language: str | None = None):
    items = DATA.get("snippets", [])
    if language and language != "any":
        items = [i for i in items if i.get("language") == language]
    if q:
        items = search_items(items, q, ["title", "description", "tags", "use_case"])
    return {"results": items[:10], "total": len(items)}


@app.get("/api/v1/snippets/{id}")
async def get_snippet(id: str):
    item = find_by_id(DATA.get("snippets", []), id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.get("/api/v1/troubleshooting")
async def list_troubleshooting(q: str | None = None, category: str | None = None):
    items = DATA.get("troubleshooting", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    if q:
        items = search_items(items, q, ["title", "symptoms", "causes", "tags"])
    return {"results": items[:10], "total": len(items)}


@app.get("/api/v1/troubleshooting/{id}")
async def get_troubleshooting_by_id(id: str):
    item = find_by_id(DATA.get("troubleshooting", []), id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.get("/api/v1/tips")
async def list_tips(category: str | None = None):
    items = DATA.get("tips", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    return {"results": items, "total": len(items)}


@app.get("/api/v1/governance/{feature}")
async def get_governance(feature: str):
    feature_lower = feature.lower().replace(" ", "-").replace("_", "-")
    for item in DATA.get("governance", []):
        if item.get("feature") == feature_lower or feature_lower in item.get("feature", ""):
            return item
    for item in DATA.get("governance", []):
        if feature_lower in item.get("display_name", "").lower():
            return item
    raise HTTPException(status_code=404, detail=f"No governance info for: {feature}")


# ---------------------------------------------------------------------------
# MCP Server (FastMCP — Streamable HTTP, stateless)
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "MCS Best Practices",
    instructions=(
        "Curated Copilot Studio best practices, code snippets, troubleshooting guides, "
        "tips, and governance zone information for the MCS Governance Bootcamp."
    ),
)


@mcp.tool()
def search_best_practices(query: str, category: str | None = None, difficulty: str | None = None) -> str:
    """Search curated Copilot Studio best practices. Returns matching practices with title and rationale."""
    items = DATA.get("best_practices", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    if difficulty:
        items = [i for i in items if i.get("difficulty") == difficulty]
    results = search_items(items, query, ["title", "description", "tags", "rationale"])
    if not results:
        return "No best practices found matching your query."
    lines = []
    for i, item in enumerate(results[:5], 1):
        lines.append(f"\n## {i}. {item['title']}")
        lines.append(f"**Description**: {item['description']}")
        lines.append(f"**Rationale**: {item.get('rationale', '')}")
        lines.append(f"*Difficulty: {item.get('difficulty', 'N/A')}*")
        lines.append(f"Resource URI: bestpractice://{item['id']}")
    return "\n".join(lines)


@mcp.tool()
def get_code_snippet(query: str, language: str | None = None) -> str:
    """Get copy-paste ready code snippets for Copilot Studio. Supports power-fx, yaml, json, or any language."""
    items = DATA.get("snippets", [])
    if language and language != "any":
        items = [i for i in items if i.get("language") == language]
    results = search_items(items, query, ["title", "description", "use_case", "tags"])
    if not results:
        return "No code snippets found matching your query."
    lines = []
    for item in results[:3]:
        lines.append(f"\n## {item['title']}")
        lines.append(f"**Language**: {item.get('language', 'unknown')}")
        lines.append(f"**Use case**: {item.get('use_case', '')}")
        lines.append(f"\n```{item.get('language', '')}\n{item.get('code', '')}\n```")
        lines.append(f"\n**Explanation**: {item.get('explanation', '')}")
        lines.append(f"Resource URI: snippet://{item['id']}")
    return "\n".join(lines)


@mcp.tool()
def troubleshoot_issue(issue: str) -> str:
    """Get step-by-step troubleshooting for Copilot Studio issues. Describe the problem or error message."""
    results = search_items(DATA.get("troubleshooting", []), issue, ["title", "symptoms", "causes", "tags"])
    if not results:
        return "No troubleshooting guides found for this issue."
    item = results[0]
    lines = [f"# {item['title']}"]
    if item.get("symptoms"):
        lines.append("\n**Symptoms**:")
        for s in item["symptoms"]:
            lines.append(f"- {s}")
    if item.get("causes"):
        lines.append("\n**Possible causes**:")
        for c in item["causes"]:
            lines.append(f"- {c}")
    if item.get("steps"):
        lines.append("\n**Resolution steps**:")
        for step in item["steps"]:
            lines.append(f"\n**Step {step['step']}**: {step['action']}")
            lines.append(f"  {step['details']}")
    lines.append(f"\nResource URI: troubleshooting://{item['id']}")
    if len(results) > 1:
        lines.append("\n**Other related guides**:")
        for other in results[1:3]:
            lines.append(f"- {other['title']} (troubleshooting://{other['id']})")
    return "\n".join(lines)


@mcp.tool()
def get_tips_for_feature(feature: str) -> str:
    """Get tips and tricks for a specific Copilot Studio feature like topics, testing, authoring, etc."""
    feature_lower = feature.lower()
    results = [
        t
        for t in DATA.get("tips", [])
        if feature_lower in t.get("category", "").lower()
        or feature_lower in t.get("title", "").lower()
        or feature_lower in " ".join(t.get("tags", [])).lower()
    ]
    if not results:
        return f"No tips found for '{feature}'."
    lines = []
    for item in results[:5]:
        lines.append(f"\n## {item['title']}")
        lines.append(item.get("tip", ""))
        if item.get("why_it_matters"):
            lines.append(f"\n*Why it matters*: {item['why_it_matters']}")
        lines.append(f"Resource URI: tip://{item['id']}")
    return "\n".join(lines)


@mcp.tool()
def check_governance_zone(feature: str) -> str:
    """Check what governance zone is required for a Copilot Studio feature like http-connector, mcp-servers, etc."""
    feature_lower = feature.lower().replace(" ", "-").replace("_", "-")
    result = None
    for item in DATA.get("governance", []):
        if feature_lower in item.get("feature", "") or feature_lower in item.get("display_name", "").lower():
            result = item
            break
    if not result:
        return f"No governance information found for '{feature}'."
    return format_governance_full(result) + f"\n\nResource URI: governance://{result['feature']}"


# ---------------------------------------------------------------------------
# MCP Resources (templates — CS calls resources/read for full detail)
# ---------------------------------------------------------------------------


@mcp.resource("bestpractice://{id}")
def get_best_practice_resource(id: str) -> str:
    """Full best practice detail including description, rationale, examples, difficulty, and tags."""
    item = find_by_id(DATA.get("best_practices", []), id)
    return format_best_practice_full(item) if item else f"Best practice '{id}' not found."


@mcp.resource("snippet://{id}")
def get_snippet_resource(id: str) -> str:
    """Full code snippet with code block, explanation, and use case."""
    item = find_by_id(DATA.get("snippets", []), id)
    return format_snippet_full(item) if item else f"Snippet '{id}' not found."


@mcp.resource("troubleshooting://{id}")
def get_troubleshooting_resource(id: str) -> str:
    """Full troubleshooting guide with symptoms, causes, and step-by-step resolution."""
    item = find_by_id(DATA.get("troubleshooting", []), id)
    return format_troubleshooting_full(item) if item else f"Troubleshooting guide '{id}' not found."


@mcp.resource("tip://{id}")
def get_tip_resource(id: str) -> str:
    """Full tip with explanation and why it matters."""
    item = find_by_id(DATA.get("tips", []), id)
    return format_tip_full(item) if item else f"Tip '{id}' not found."


@mcp.resource("governance://{feature}")
def get_governance_resource(feature: str) -> str:
    """Full governance zone information including availability per zone and justification template."""
    feature_lower = feature.lower().replace(" ", "-").replace("_", "-")
    for item in DATA.get("governance", []):
        if item.get("feature") == feature_lower:
            return format_governance_full(item)
    return f"Governance info for '{feature}' not found."


# ---------------------------------------------------------------------------
# Mount MCP on FastAPI
# ---------------------------------------------------------------------------

_mcp_asgi_app = mcp.http_app(path="/", stateless_http=True)
app.mount("/mcp", _mcp_asgi_app)

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "2011"))
    uvicorn.run(app, host="0.0.0.0", port=port)
