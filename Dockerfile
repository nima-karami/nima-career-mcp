FROM python:3.12-slim

# Pinned (not :latest) so the build can't pull a different toolchain under the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

WORKDIR /app

# Dependencies first for layer caching. README is referenced by pyproject.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

COPY corpus ./corpus
ENV NIMA_CORPUS_DIR=/app/corpus

ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["uvicorn", "nima_career_mcp.server:app", "--host", "0.0.0.0", "--port", "8080"]
