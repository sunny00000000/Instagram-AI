FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      ffmpeg \
      fonts-dejavu-core \
      tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.lock pyproject.toml README.md LICENSE ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --require-hashes -r requirements.lock
COPY src ./src
RUN python -m pip install --no-deps .

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /app/data/media /app/logs \
    && chown -R app:app /app

USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail http://127.0.0.1:8080/health || exit 1
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["cryptopulse", "serve", "--host", "0.0.0.0", "--port", "8080"]
