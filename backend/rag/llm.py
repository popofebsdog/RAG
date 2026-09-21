from __future__ import annotations

import os

import httpx

from .retrieval import RetrievalResult


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:12b-it-q4_K_M"

SYSTEM_PROMPT = (
    "你是一個精準的文件助理。"
    "請完全根據提供的上下文與因果關係回答問題。"
    "如果答案不在上下文中，請明確說明。"
    "回答要簡潔，並說明資訊來源。"
)


def _ollama_chat(system: str, user: str) -> str:
    ollama_url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    response = httpx.post(
        f"{ollama_url}/api/chat",
        json={
            "model": ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def generate_answer(
    query: str,
    results: list[RetrievalResult],
    relations: list[dict] | None = None,
) -> str:
    """Generate an answer from local retrieval context with Ollama."""
    context_parts: list[str] = []
    for result in results:
        if result.is_boosted:
            label = (
                result.chunk.chunk_id.split(":")[1]
                if result.chunk.chunk_id.startswith("manual:")
                else result.chunk.chunk_id
            )
            context_parts.append(
                f"[概念節點：{label}（知識圖譜）]\n"
                f"佐證內容：{result.chunk.text[:400]}"
            )
        else:
            context_parts.append(
                f"[段落 {result.chunk.chunk_id} | 頁 {result.chunk.source_page}]\n"
                f"{result.chunk.text}"
            )
    context = "\n\n---\n\n".join(context_parts)

    retrieved_ids = {result.chunk.chunk_id for result in results}
    relation_lines: list[str] = []
    for relation in relations or []:
        if (
            relation.get("from_chunk_id") in retrieved_ids
            or relation.get("to_chunk_id") in retrieved_ids
        ):
            from_name = relation.get("from_label") or (
                relation.get("from_text") or relation.get("from_chunk_id", "?")
            )[:40]
            to_name = relation.get("to_label") or (
                relation.get("to_text") or relation.get("to_chunk_id", "?")
            )[:40]
            relation_lines.append(
                f"  「{from_name}」 --[{relation.get('label', '→')}]--> 「{to_name}」"
            )

    relation_section = ""
    if relation_lines:
        relation_section = "\n\n【已知圖譜關係】\n" + "\n".join(relation_lines) + "\n"

    user_message = f"上下文：\n{context}{relation_section}\n\n問題：{query}"
    return _ollama_chat(SYSTEM_PROMPT, user_message)
