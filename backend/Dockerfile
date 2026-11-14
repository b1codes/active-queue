# ActiveQueue API image (Cloud Run). CI builds it on every PR, lints it with hadolint,
# scans it with Trivy, and starts it against the emulators for the smoke check (ci.yml
# `container` job). Base images are pinned by digest. Dependabot bumps them.

# --- Build: resolve the locked production dependencies into /app/.venv -------------------
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.2@sha256:b9fddcde095a7aeafd499024adb8927df6619c7c5672f5ff7126474715f62ba4 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Runtime: no uv, no build tools, unprivileged user ----------------------------------
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

# Pick up Debian security fixes released since the base image was built (Trivy fails the
# build on fixable HIGH/CRITICAL OS findings), then add an unprivileged user.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin api

WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY app/ ./app/

USER 10001
EXPOSE 8080

# Run uvicorn from the venv directly. `uv run` would re-sync the project at every start,
# installing the dev dependency group from PyPI on each Cloud Run cold start.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
