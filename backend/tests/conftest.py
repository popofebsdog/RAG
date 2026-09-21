from __future__ import annotations

import os


os.environ.setdefault("RAG_API_KEY", "test-rag-api-key")
os.environ.setdefault("RAG_AUTH_ENABLED", "1")
os.environ.setdefault("OLLAMA_MODEL", "gemma4:12b-it-q4_K_M")
os.environ.setdefault("OLLAMA_VISION_MODEL", "gemma4:12b-it-q4_K_M")
