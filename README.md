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

### Option A: MCP Server (recommended)

1. In Copilot Studio, go to **Tools > Add Tool**
2. Select **MCP Server**
3. Enter server URL: `https://your-server/mcp`
4. Add authentication: API Key in `X-API-Key` header, value: `mcs-bootcamp-2025`
5. Test connection and select tools

### Option B: REST API via Custom Connector

#### 1. Upload specification

1. In Copilot Studio, go to **Tools > Add Tool**
2. Click **Upload specification**
3. Upload `swagger-rest.yaml` (included in this repo)

#### 2. Authentication

| Field | Value |
|-------|-------|
| Authentication type | API Key |
| Parameter label | `API Key` |
| Parameter name | `X-API-Key` |
| Parameter location | Header |

#### 3. Review tool parameters

After uploading, Copilot Studio will list each API operation as a tool. Review and update the input/output descriptions for each:

---

**Search best practices** (`ListBestPractices`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| q | Search query (matches title, description, tags) |
| category | Filter by category (e.g. topics, security, connectors, variables, testing) |
| difficulty | Filter by difficulty (beginner, intermediate, advanced) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Best practice ID (e.g. bp-001) |
| title | Name of the best practice |
| category | Category (topics, security, connectors, variables, testing) |
| description | What the best practice recommends |
| rationale | Why this practice matters |
| example_good | Example of correct implementation |
| example_bad | Example of what to avoid |
| difficulty | Skill level (beginner, intermediate, advanced) |
| total | Number of results returned |

---

**Get best practice by ID** (`GetBestPractice`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| id | Best practice ID (e.g. bp-001) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Best practice ID |
| title | Name of the best practice |
| category | Category |
| description | What the best practice recommends |
| rationale | Why this practice matters |
| example_good | Example of correct implementation |
| example_bad | Example of what to avoid |
| difficulty | Skill level |
| tags | Related keywords |

---

**Search code snippets** (`ListSnippets`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| q | Search query (matches title, description, code) |
| language | Filter by language (power-fx, yaml, json, any) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Snippet ID (e.g. snip-001) |
| title | Name of the snippet |
| language | Programming language (power-fx, yaml, json) |
| category | Snippet category |
| description | What the snippet does |
| code | The code snippet (copy-paste ready) |
| explanation | How the code works |
| use_case | When to use this snippet |
| total | Number of results returned |

---

**Get snippet by ID** (`GetSnippet`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| id | Snippet ID (e.g. snip-001) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Snippet ID |
| title | Name of the snippet |
| language | Programming language |
| category | Snippet category |
| description | What the snippet does |
| code | The code snippet (copy-paste ready) |
| explanation | How the code works |
| use_case | When to use this snippet |

---

**Search troubleshooting guides** (`ListTroubleshooting`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| q | Search query (matches title, symptoms, causes) |
| category | Filter by category (e.g. connectors, publishing, auth) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Troubleshooting ID (e.g. ts-001) |
| title | Issue title |
| category | Issue category |
| symptoms | What you see when this issue occurs |
| causes | Common root causes |
| resolution_steps | Step-by-step fix instructions |
| total | Number of results returned |

---

**Get troubleshooting guide by ID** (`GetTroubleshooting`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| id | Troubleshooting ID (e.g. ts-001) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Troubleshooting ID |
| title | Issue title |
| category | Issue category |
| symptoms | What you see when this issue occurs |
| causes | Common root causes |
| resolution_steps | Step-by-step fix instructions |

---

**List tips** (`ListTips`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| category | Filter by category (e.g. testing, authoring, publishing) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Tip ID (e.g. tip-001) |
| title | Tip title |
| category | Tip category |
| tip | The actual tip text |
| why_it_matters | Why this tip is important |
| tags | Related keywords |
| total | Number of results returned |

---

**Get governance zone info** (`GetGovernance`)

Inputs:

| Parameter | Description |
|-----------|-------------|
| feature | Feature name (e.g. http-connector, mcp-servers, ai-builder) |

Outputs:

| Parameter | Description |
|-----------|-------------|
| id | Governance ID (e.g. gov-001) |
| feature | Feature identifier |
| display_name | Human-readable feature name |
| minimum_zone | Minimum governance zone required (green, yellow, red, red-extra) |
| zones | Availability and requirements per zone |
| justification_template | Template for requesting access to this feature |

---

#### 4. Review and Publish

1. Review all tools and their descriptions
2. Click **Publish** to make the tools available to your agent
