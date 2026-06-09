# Stateless Streamable-HTTP MCP server, served by uvicorn behind Fly's TLS.
FROM python:3.12-slim

# Install uv (fast, reproducible installs). Pinned, not `:latest`, so the build can't pull a
# different toolchain out from under the committed uv.lock (supply-chain / reproducibility).
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

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

# Drop root: the server only ever reads /app, so run as an unprivileged user (defense in
# depth — a process bug can't write the image or escalate within the container).
RUN useradd --create-home --uid 10001 appuser
USER appuser

# server:app is the middleware-wrapped ASGI app (rate limit + Origin + Host + size caps).
CMD ["uvicorn", "nima_career_mcp.server:app", "--host", "0.0.0.0", "--port", "8080"]
