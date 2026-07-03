FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ops/admin/ /app/ops/admin/
COPY ops/xui/ /app/ops/xui/

RUN groupadd --system --gid 10001 mirage \
  && useradd --system --uid 10001 --gid mirage --home-dir /nonexistent --shell /usr/sbin/nologin mirage \
  && mkdir -p /data/backups /data/alerts \
  && chown -R mirage:mirage /data

USER 10001:10001

ENTRYPOINT ["python", "/app/ops/admin/admin_api.py"]
