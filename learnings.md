# Learnings: MCP + REST API with Copilot Studio

Workarounds discovered while connecting a FastMCP + FastAPI server to Copilot Studio via Custom Connectors.

## MCP Server Issues

### 1. Azure API Hub strips the `Accept` header

**Problem:** FastMCP requires `Accept: application/json, text/event-stream` on POST requests. Azure API Hub proxy strips this header, causing a 406 Not Acceptable response.

**Fix:** Middleware that injects the Accept header for POST `/mcp` requests if missing.

```python
@app.middleware("http")
async def mcp_accept_middleware(request, call_next):
    if request.url.path.startswith("/mcp") and request.method == "POST":
        accept = request.headers.get("accept", "")
        if "text/event-stream" not in accept:
            headers = dict(request.scope["headers"])
            headers[b"accept"] = b"application/json, text/event-stream"
            request.scope["headers"] = list(headers.items())
    return await call_next(request)
```

### 2. Connector validation sends GET to MCP endpoint

**Problem:** Custom Connector test/validation sends a GET request to the MCP endpoint. FastMCP only handles POST (MCP protocol) and rejects GET with 406 even after the Accept header fix.

**Fix:** Intercept GET requests on `/mcp` in auth middleware and return a simple JSON status response instead of forwarding to FastMCP.

```python
if request.url.path.startswith("/mcp") and request.method == "GET":
    return JSONResponse({"status": "ok", "server": "MCS Best Practices MCP", "protocol": "mcp-streamable-1.0"})
```

### 3. Starlette Mount redirects `/mcp` to `/mcp/`

**Problem:** `app.mount("/mcp", mcp_app)` causes Starlette to 307 redirect `POST /mcp` to `POST /mcp/`. This breaks clients that don't follow redirects.

**Fix:** Clients (httpx in tests) need `follow_redirects=True`. In production this is transparent since browsers/API Hub follow redirects.

### 4. MCP SSE response format

**Problem:** MCP Streamable HTTP returns Server-Sent Events format (`event: message\ndata: {...}`), not plain JSON. Parsing `response.json()` fails.

**Fix:** Parse SSE data lines to extract JSON:

```python
def parse_sse_json(text):
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}
```

### 5. FastMCP session manager is single-use in tests

**Problem:** FastMCP's `StreamableHTTPSessionManager` can only have its lifespan called once. Running multiple MCP tests with a shared fixture fails with "can only be called once per instance".

**Fix:** Create a fresh `mcp.http_app()` per test and temporarily swap the mounted route:

```python
@pytest.fixture
async def mcp_client():
    fresh_mcp_app = mcp.http_app(path="/", stateless_http=True)
    # swap mount, run lifespan, yield client, restore mount
```

### 6. anyio cancel scope teardown error in tests

**Problem:** FastMCP's session manager task group uses anyio cancel scopes. When pytest-asyncio tears down the fixture, it exits the cancel scope in a different async task than it was entered in, causing `RuntimeError`.

**Fix:** Manually manage the async context manager and suppress the RuntimeError on teardown:

```python
ctx = fresh_mcp_app.lifespan(fresh_mcp_app)
await ctx.__aenter__()
try:
    yield client
finally:
    try:
        await ctx.__aexit__(None, None, None)
    except RuntimeError:
        pass  # harmless teardown artifact
```

## REST API Issues

### 7. CORS preflight blocked by auth middleware

**Problem:** Browsers and Azure API Hub send `OPTIONS` preflight requests before actual API calls. These don't carry the `X-API-Key` header, so auth middleware returns 401.

**Fix:** Two changes:
1. Add `CORSMiddleware` to FastAPI with `allow_origins=["*"]`
2. Skip auth for all `OPTIONS` requests

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In auth middleware:
if request.url.path == "/health" or request.method == "OPTIONS":
    return await call_next(request)
```

### 8. Swagger spec: no `$ref`, no arrays for Copilot Studio

**Problem:** Copilot Studio's Custom Connector tool parameter extraction doesn't handle `$ref` references or `type: array` fields well. Tools show empty or broken parameter lists.

**Fix:** In the swagger spec:
- Inline all schemas (no `$ref`, no `definitions` block)
- Change all `type: array` fields to `type: string` (describe as comma-separated in description)
- Change `type: object` without properties to `type: string`

### 9. Swagger spec: `x-ms-agentic-protocol` is an OpenAPI annotation

**Problem:** `x-ms-agentic-protocol: mcp-streamable-1.0` is NOT an HTTP header to send. It's an annotation in the OpenAPI spec on the POST operation that tells Copilot Studio this connector speaks MCP.

**Fix:** Only add it to the swagger YAML under the POST operation, not as a request header:

```yaml
paths:
  /:
    post:
      x-ms-agentic-protocol: mcp-streamable-1.0
```

## Summary

| # | Issue | Layer | Root Cause |
|---|-------|-------|------------|
| 1 | Accept header stripped | MCP | Azure API Hub proxy |
| 2 | GET validation on MCP endpoint | MCP | Connector test behavior |
| 3 | 307 redirect on mount | MCP | Starlette Mount behavior |
| 4 | SSE response format | MCP | MCP protocol spec |
| 5 | Single-use session manager | MCP | FastMCP test limitation |
| 6 | Cancel scope teardown | MCP | anyio + pytest-asyncio |
| 7 | CORS preflight blocked | REST | Browser security model |
| 8 | $ref and arrays in swagger | REST | Copilot Studio limitations |
| 9 | x-ms-agentic-protocol misuse | MCP | Documentation confusion |
