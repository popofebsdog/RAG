FROM node:22-alpine AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && for dir in data source_cache pages_cache graphs_cache markdown_cache relations_cache ocr_cache vlm_cache images_cache; do \
         mkdir -p "/data/$dir"; \
         rm -rf "/app/backend/$dir"; \
         ln -s "/data/$dir" "/app/backend/$dir"; \
       done \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R app:app /app /data

USER app
WORKDIR /app/backend

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
