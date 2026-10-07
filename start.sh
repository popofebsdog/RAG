#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  printf 'POSTGRES_PASSWORD=%s\nAPP_PORT=8000\nOLLAMA_VERSION=0.34.2\nOLLAMA_MODEL=gemma4:12b-it-q4_K_M\nEMBED_MODEL=nomic-embed-text\n' "$(openssl rand -hex 32)" > .env
  chmod 600 .env
fi

POSTGRES_PASSWORD=$(sed -n 's/^POSTGRES_PASSWORD=//p' .env | head -1)
if [ -z "$POSTGRES_PASSWORD" ]; then
  echo "POSTGRES_PASSWORD is missing from .env"
  exit 1
fi
if [[ ! "$POSTGRES_PASSWORD" =~ ^[A-Za-z0-9._~-]+$ ]]; then
  echo "POSTGRES_PASSWORD may contain only letters, numbers, and . _ ~ -"
  exit 1
fi

APP_PORT=$(sed -n 's/^APP_PORT=//p' .env | head -1)
APP_PORT=${APP_PORT:-8000}
if [[ ! "$APP_PORT" =~ ^[0-9]+$ ]] || [ "$APP_PORT" -lt 1 ] || [ "$APP_PORT" -gt 65535 ]; then
  echo "APP_PORT must be a number from 1 to 65535"
  exit 1
fi

chmod 600 .env

docker compose up -d postgres
for _ in {1..30}; do
  if docker compose exec -T postgres pg_isready -U visual_rag -d visual_rag >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! docker compose exec -T postgres pg_isready -U visual_rag -d visual_rag >/dev/null 2>&1; then
  echo "PostgreSQL did not become ready"
  exit 1
fi
printf "ALTER ROLE visual_rag WITH PASSWORD '%s';\n" "$POSTGRES_PASSWORD" \
  | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U visual_rag -d visual_rag >/dev/null

echo "Building and starting containerized Visual RAG services..."
docker compose up -d --build --wait

echo "Visual RAG is available on the intranet at http://<server-ip>:$APP_PORT"
docker compose ps
