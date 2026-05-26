#!/bin/bash
set -e

echo "Starting Visual RAG System..."

# Backend
(
  cd backend
  if [ ! -d ".venv" ]; then
    echo "Creating Python venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
  else
    source .venv/bin/activate
  fi

  if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created backend/.env — set ANTHROPIC_API_KEY before continuing"
    exit 1
  fi

  uvicorn main:app --reload --port 8000 &
  echo "✓ Backend running at http://localhost:8000"
) &

# Frontend
(
  cd frontend
  [ ! -d "node_modules" ] && npm install
  npm run dev &
  echo "✓ Frontend running at http://localhost:5173"
) &

wait
