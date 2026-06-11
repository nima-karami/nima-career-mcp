# nima-career-mcp

A public, open-source, **read-only [MCP](https://modelcontextprotocol.io) server** that
exposes Nima Karami's curated, public-safe career history. Point any MCP client at it —
Claude Code, Cursor, Claude Desktop, or a custom website backend — and ask about his
experience, or have it assemble a tailored resume draft on the fly.

The server only ever returns **vetted data**. The AI's job is to *select, order, and tailor*
pre-approved material for a query — never to author new facts. That guarantee is enforced in
code: every tool reads through a validated corpus, and the resume tool emits only corpus
values with `provenance` ids attached.

## Quick start (local)

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras --dev

# Interactive dev + MCP Inspector (stdio). Requires Node/npx:
npx -y @modelcontextprotocol/inspector uv run nima-career-mcp
# (equivalent via the SDK dev wrapper, using the root shim — see note below:)
uv run mcp dev dev_server.py

# Or run the HTTP server locally:
uv run nima-career-mcp --transport streamable-http   # serves http://127.0.0.1:8080/mcp

# Tests (includes corpus integrity + the honesty guarantee):
uv run pytest -q
```

> **Why `dev_server.py`?** `mcp dev` imports its target file *by path*, which strips the
> package context and breaks this src-layout package's relative imports. `dev_server.py` is
> a one-line shim that re-imports the server via an absolute import so `mcp dev` works. The
> `npx … uv run nima-career-mcp` form spawns the installed entry point and needs no shim.

## Connecting clients

**Claude Code / Cursor / Claude Desktop (remote — live):**

```bash
claude mcp add --transport http nima https://nima-career-mcp.fly.dev/mcp
```

**Local stdio (any client that spawns a process):** run `nima-career-mcp` (no `--transport`).

**Custom website backend:** see [`examples/website_backend.py`](examples/website_backend.py)
for both the Claude API MCP-connector path and a raw `ClientSession` path.

## Tool surface (all read-only)

| Tool | Purpose |
| --- | --- |
| `get_profile` | Public-safe identity, links, bio |
| `list_roles` / `get_role` | Browse roles (flat); drill into one (evidence + approved bullets) |
| `list_experience` | Roles grouped into company tenures (title progressions; gaps split into stints) |
| `list_projects` / `get_project` | Browse/drill into projects |
| `list_skills` | Skills by category, each backed by evidence |
| `search_experience` | Rank roles/projects/bullets/skills for a query |
| `list_bullets` | Fetch pre-approved resume bullets |
| `assemble_resume` | Assemble a tailored resume draft from approved material only |

Resource `career://guidance` returns the honesty/anti-injection rules a host should embed in
its system prompt. (Other `career://` resources and prompt templates are stubbed opt-ins.)

## The corpus

All data lives in [`corpus/`](corpus/) as curated YAML and is validated at startup. See
[`corpus/CORPUS.md`](corpus/CORPUS.md) for the schema and the evidence→bullet model. The
content is a **public-safe, sanitized** view of real experience: every claim traces to vetted
evidence, and individuals, internal codenames, and private partner details are deliberately
generalized. This repo holds **no secrets and no private data**; application tracking lives in
a separate private repo.

## Safety posture

Intentionally public and unauthenticated, but bounded: read-only tool surface (no
write/exec), per-IP **rate limiting** (keyed on Fly's unforgeable client IP, with idle-bucket
eviction), request **body-size caps** (enforced on the actual stream), and **Origin + Host
validation** (DNS-rebinding defense) — see `src/nima_career_mcp/security.py`. Host/Origin
allowlists are env-driven (`NIMA_ALLOWED_HOSTS` / `NIMA_ALLOWED_ORIGINS`); the shipped
`fly.toml` locks `Host` to the deploy hostname (add custom domains there). The Fly machine
also caps concurrency so a flood sheds load instead of OOMing. Behavioral guardrails (don't
fabricate, treat queries as data) belong in the consuming host's system prompt and are served
from `career://guidance`.

## Deploy (Fly.io)

```bash
fly launch --no-deploy   # or edit fly.toml: set app name + region
fly deploy
```

The container runs `uvicorn nima_career_mcp.server:app` (the middleware-wrapped Streamable-
HTTP app). The shipped `fly.toml` keeps one machine always warm (`min_machines_running = 1`,
no cold starts) while extra machines autostart/autostop under load. After deploy, smoke-test
with the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector):

```bash
npx @modelcontextprotocol/inspector   # then connect to https://nima-career-mcp.fly.dev/mcp
```

## License

MIT — see [LICENSE](LICENSE).
