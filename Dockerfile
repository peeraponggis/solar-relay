# syntax=docker/dockerfile:1.7
# ---- build wheels once (keeps gcc out of the runtime image) ----
FROM python:3.12-slim AS build
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY solar_relay ./solar_relay
RUN pip wheel --no-cache-dir --wheel-dir /wheels ".[all]"

# ---- runtime ----
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/peeraponggis/solar-relay" \
      org.opencontainers.image.title="solar-relay" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN groupadd -r relay && useradd -r -g relay -G dialout -d /app relay \
    && mkdir -p /app /config && chown relay:relay /app /config
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
USER relay
VOLUME ["/config"]
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import solar_relay, sys; sys.exit(0)"
ENTRYPOINT ["solar-relay", "--config", "/config/config.yaml"]
