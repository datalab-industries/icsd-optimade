FROM ghcr.io/astral-sh/uv:0.9.21 AS uv
FROM python:3.13-slim-trixie AS base

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_DEV=1 \
    UV_PROJECT_ENVIRONMENT=/opt/.venv \
    UV_PYTHON=python3.13

WORKDIR /app

COPY LICENSE pyproject.toml uv.lock ./
COPY src /app/src

RUN uv sync --locked

CMD ["uv", "run", "optimake", "serve", "."]
