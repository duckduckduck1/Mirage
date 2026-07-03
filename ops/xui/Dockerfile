FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ops/xui/ /app/ops/xui/

ENTRYPOINT ["python", "/app/ops/xui/xui_api.py"]
