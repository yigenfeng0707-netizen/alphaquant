# AlphaQuant — ModelScope Studio Docker image
# Same-origin: Vue dist is served by FastAPI. Listen on 0.0.0.0:$PORT (default 7860).
FROM node:20-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN node -e "const fs=require('fs'); const p=JSON.parse(fs.readFileSync('package.json','utf8')); if (p.devDependencies) delete p.devDependencies.playwright; fs.writeFileSync('package.json', JSON.stringify(p, null, 2));"
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    PYTHONPATH=/app/backend \
    STATIC_DIR=/app/frontend/dist

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/ /app/backend/
COPY data/offline/ /app/data/offline/
COPY --from=frontend /web/dist /app/frontend/dist

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://127.0.0.1:7860/health || exit 1

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
