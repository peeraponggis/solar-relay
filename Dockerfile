FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY solar_relay ./solar_relay
RUN pip install --no-cache-dir ".[all]"
VOLUME ["/config"]
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["solar-relay", "--config", "/config/config.yaml"]
