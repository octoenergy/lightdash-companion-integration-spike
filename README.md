# Lightdash ↔ Companion integration spike

A throwaway "fake Companion": a small chat app that talks to the Lightdash MCP, used to prove which
integration capabilities are possible. It does not depend on neuralink or kraken-core.

Results are in [`docs/findings.md`](docs/findings.md).

## Setup

Requires `uv` (Python 3.13) and Node.

```sh
uv sync
cd web && npm install && cd ..
cp .env.example .env   # then fill it in
```

`.env` settings:

| Variable | Needed for |
|---|---|
| `LIGHTDASH_URL`, `LIGHTDASH_TOKEN`, `PROJECT_UUID` | everything (a PAT with `manage:Explore`) |
| `OPENAI_API_KEY` | the chat agent |
| `EMBED_SECRET` | Explore from here |
| `SANDBOX_SPACE_SLUG` | Save chart. Charts are written into this space on the **real** instance, so use a dedicated empty one. |
| `LIGHTDASH_ADMIN_TOKEN` | row-level security (an org-admin token) |
| `AGENT_UUID` | agent scoping. Leave blank to use the full project scope. |

Blank optional values are treated as unset.

## Run the app

```sh
cd web && npm run build && cd ..
uv run uvicorn lightdash_companion_integration_spike.api.app:create_default_app --factory --port 8000
```

Open http://localhost:8000. FastAPI serves the built `web/dist`, and chat history is stored in
`spike.sqlite3` (git-ignored).

For frontend work with hot reload, run the API as above and `npm run dev` in `web/`. Vite proxies
`/api` to port 8000.

## Tests

```sh
uv run pytest                 # unit and functional tests, no network or credentials needed
cd web && npx tsc --noEmit    # typecheck the frontend
```

The tests fake the MCP, so they run offline. Fixtures are in `tests/fixtures/`.

## Live checks (need `.env`)

These call the real KTL instance:

```sh
uv run python scripts/probe_mcp.py                      # connects, lists tools, runs one query, prints the response shape
uv run python scripts/ask_agent.py "your question"      # asks the agent one question end to end
```

`ask_agent.py` uses an in-memory database. The probe only reads. The Save button
(`POST /api/charts/save`) writes a chart into `SANDBOX_SPACE_SLUG`, and nothing deletes it, so
remove test charts in Lightdash yourself.

## Layout

```
src/lightdash_companion_integration_spike/
  lightdash/   MCP client, query runner, content (save), embed token, user-attribute header
  agent/       PydanticAI agent, tool-result summary, history replay
  domain/      typed blocks, artifact versions, query spec
  storage/     SQLite threads, messages, artifact versions, feedback
  api/         FastAPI routes (SSE answer stream, rerun, explore-url, save, feedback)
web/src/       chat page, chart card, chart rendering with @lightdash/visualization
```

`@lightdash/visualization` and `@lightdash/common` are pinned to `2.427.4` to match the KTL
instance. Bump them together if the instance is upgraded.
