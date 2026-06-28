FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ops/xui/xui_api.py /app/xui_api.py

ENTRYPOINT ["python", "/app/xui_api.py"]
