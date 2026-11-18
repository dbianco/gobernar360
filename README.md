# gobernar360

Workspace of management dashboards for local governments (municipalities and
communes). Each dashboard is an independent module, enabled per municipality
and granted per user.

- Design: `docs/superpowers/specs/2026-11-18-gobernar360-platform-design.md`
- Functional reference: `tableros-de-gestion-portal-ril.md`

## Development

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js.

```bash
docker compose up -d db          # PostgreSQL/PostGIS on localhost:5434

cd backend
uv run uvicorn gobernar360.main:create_app --factory --reload --port 8000
uv run pytest                    # tests run against the gobernar360_test database
uv run ruff check .
```

Configuration is read from `GOBERNAR360_*` environment variables; see
`backend/src/gobernar360/core/config.py` for the defaults.
