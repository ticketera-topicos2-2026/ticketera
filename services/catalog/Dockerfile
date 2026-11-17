# Catalog service image (DS-11, DS-13, DS-14, DS-25).
FROM ghcr.io/astral-sh/uv:0.9.9@sha256:f6e3549ed287fee0ddde2460a2a74a2d74366f84b04aaa34c1f19fec40da8652 AS uv

FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72

# Host user IDs, so files created in mounted folders belong to the host user (DS-13).
ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:${PATH}"

COPY --from=uv /uv /usr/local/bin/uv

RUN groupadd --gid "${GID}" app \
    && useradd --uid "${UID}" --gid "${GID}" --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /opt/venv /app \
    && chown app:app /opt/venv /app

USER app
WORKDIR /app

# Dependencies only from the lockfile (DS-25); the environment lives outside the bind mount (DS-14).
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY --chown=app:app . .

EXPOSE 8000
CMD ["uvicorn", "catalog.api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
