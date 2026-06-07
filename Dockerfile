# Stateless Streamable-HTTP MCP server, served by uvicorn behind Fly's TLS.
FROM python:3.12-slim

# Install uv (fast, reproducible installs).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (better layer caching). README is referenced by pyproject.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# The public-safe corpus is read at startup.
COPY corpus ./corpus
ENV NIMA_CORPUS_DIR=/app/corpus

# Bind to all interfaces inside the container; Fly terminates TLS in front.
ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

# server:app is the middleware-wrapped ASGI app (rate limit + Origin + size caps).
CMD ["uvicorn", "nima_career_mcp.server:app", "--host", "0.0.0.0", "--port", "8080"]
