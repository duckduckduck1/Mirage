FROM python:3.12-slim

ARG TG_WS_PROXY_VERSION=v1.6.5

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git tini \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "tg-ws-proxy @ git+https://github.com/Flowseal/tg-ws-proxy.git@${TG_WS_PROXY_VERSION}" \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

COPY ops/tg-ws-proxy/entrypoint.sh /usr/local/bin/tg-ws-proxy-entrypoint
RUN chmod +x /usr/local/bin/tg-ws-proxy-entrypoint

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/tg-ws-proxy-entrypoint"]
