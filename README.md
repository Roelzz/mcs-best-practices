# MCS Best Practices API + MCP Server

Curated Copilot Studio best practices, code snippets, troubleshooting guides, and governance zone info for the MCS Governance Bootcamp.

## Quick Start

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)

# Docker
podman-compose up --build

# Or local
uv sync
uv run python main.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEYS` | `mcs-bootcamp-2025,mcs-demo-key` | Comma-separated valid API keys |
| `PORT` | `2011` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `BASE_URL` | `https://your-server.example.com/` | Public base URL for the server |

## API Endpoints

All endpoints require `X-API-Key` header except `/health`.

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check (no auth) |
| `GET /api/v1/best-practices?q=&category=&difficulty=` | Search best practices |
| `GET /api/v1/best-practices/{id}` | Get best practice by ID |
| `GET /api/v1/snippets?q=&language=` | Search code snippets |
| `GET /api/v1/snippets/{id}` | Get snippet by ID |
| `GET /api/v1/troubleshooting?q=&category=` | Search troubleshooting guides |
| `GET /api/v1/troubleshooting/{id}` | Get troubleshooting guide by ID |
| `GET /api/v1/tips?category=` | List tips |
| `GET /api/v1/governance/{feature}` | Get governance zone info |
| `POST /mcp` | MCP Streamable HTTP endpoint |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_best_practices` | Search curated best practices by query, category, difficulty |
| `get_code_snippet` | Get Power Fx/YAML/JSON code snippets |
| `troubleshoot_issue` | Step-by-step troubleshooting for issues |
| `get_tips_for_feature` | Tips for specific features |
| `check_governance_zone` | Check zone requirements for features |

## MCP Resources

| URI Pattern | Content |
|-------------|---------|
| `bestpractice://{id}` | Full best practice detail |
| `snippet://{id}` | Full code snippet with explanation |
| `troubleshooting://{id}` | Full troubleshooting guide |
| `tip://{id}` | Full tip detail |
| `governance://{feature}` | Full governance zone matrix |

## Development

```bash
uv sync
uv run python main.py          # Run server on port 2011
uv run pytest                   # Run tests
uv run ruff check .             # Lint
uv run ruff format .            # Format
```

## Deployment

```bash
podman-compose up --build       # Build and run
podman-compose down             # Stop
```

## Copilot Studio Setup

**Via MCP Onboarding Wizard (recommended):**
1. In Copilot Studio, go to Tools > Add Tool
2. Select MCP Server
3. Enter server URL: `https://your-server:2011/mcp`
4. Add authentication: API Key in `X-API-Key` header
5. Test connection and select tools

**Via Custom Connector:**
1. Power Apps > Custom Connectors > Create from blank
2. Host: your-server (or dev tunnel for local)
3. Security: API Key, Header name: `X-API-Key`
4. Add `POST /mcp` operation with `x-ms-agentic-protocol: mcp-streamable-1.0` annotation
5. In Copilot Studio: Tools > Add Tool > MCP > Select connector
