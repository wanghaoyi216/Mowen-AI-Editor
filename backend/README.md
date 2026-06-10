# Backend

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Demo Graph Seed

```bash
python scripts/seed_demo.py
```

This creates:

- 1 demo novel project
- 3 demo characters
- 3 character relationships

If Neo4j is running with the configured credentials, the seed will also sync graph data to Neo4j.

## Production-Oriented Notes

- Docker Compose uses PostgreSQL instead of SQLite.
- Redis is included for future task queue / workflow execution support.
- Neo4j is included as the graph backend.
- SQLite dev mode still supports `create_all()` for convenience.
- PostgreSQL / container mode should use Alembic migrations.

## Alembic

Create or upgrade schema:

```bash
alembic upgrade head
```

Create a new revision:

```bash
alembic revision -m "describe change"
```

## Task Runtime State

Task runtime state now has a Redis-backed API:

- `GET /api/v1/projects/{project_id}/tasks/{task_id}/runtime`
- `POST /api/v1/projects/{project_id}/tasks/{task_id}/runtime`

## Search Integrations

The backend now supports:

- Tavily for live web search
- Firecrawl for page scraping

Provide keys through environment variables only:

```bash
FIRECRAWL_KEY=...
TAVILY_KEY=...
```

New execution endpoints:

- `POST /api/v1/projects/{project_id}/trend-explorations/execute`
- `POST /api/v1/projects/{project_id}/tasks/execute-trend-react`

The application reads these keys at runtime and does not store or echo them in project files.

## OpenRouter

NVIDIA NIM (integrate.api.nvidia.com/v1) is now the primary LLM gateway for the project.

Environment variables:

```bash
NVIDIA_API_KEY=nvapi-...         # NVIDIA NIM 平台 token
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

Capabilities:

- Discover current free / reasoning models at runtime
- Primary model `nvidia/nemotron-3-ultra-550b-a55b` (reasoning, long context)
- Sub-agent model `minimaxai/minimax-m2.7`
- Fallback chain automatically tried when primary fails

## Scope

- FastAPI API service
- SQLite/PostgreSQL persistence
- Neo4j graph integration
- AI task orchestration layer
