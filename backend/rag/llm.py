from __future__ import annotations

import os

import httpx

from .retrieval import RetrievalResult

# ── Config ────────────────────────────────────────────────────────────────────
LLM_PROVIDER   = os.getenv("LLM_PROVIDER",   "ollama")
OLLAMA_URL     = os.getenv("OLLAMA_URL",     "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",   "llama3.2")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

SYSTEM_PROMPT = (
    "你是一個精準的文件助理。"
    "請完全根據提供的上下文與因果關係回答問題。"
    "如果答案不在上下文中，請明確說明。"
    "回答要簡潔，並說明資訊來源。"
)


# ── Ollama ────────────────────────────────────────────────────────────────────

def _ollama_chat(system: str, user: str) -> str:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ── Anthropic fallback ────────────────────────────────────────────────────────

def _anthropic_chat(system: str, user: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


# ── Public API ────────────────────────────────────────────────────────────────

def generate_answer(
    query: str,
    results: list[RetrievalResult],
    relations: list[dict] | None = None,
) -> str:
    """Generate an answer from retrieved chunks.

    relations: optional list of dicts with keys from_text, to_text, label,
               from_chunk_id, to_chunk_id — injected as causal context so
               the LLM can reason about curated graph relationships.
    """
    # ── Chunk context ──────────────────────────────────────────────────────────
    context_parts: list[str] = []
    for r in results:
        if r.is_boosted:
            # Knowledge node: show label as concept name, text as supporting evidence
            label = r.chunk.chunk_id.split(":")[1] if r.chunk.chunk_id.startswith("manual:") else r.chunk.chunk_id
            context_parts.append(
                f"[概念節點：{label}（知識圖譜）]\n"
                f"佐證內容：{r.chunk.text[:400]}"
            )
        else:
            context_parts.append(
                f"[段落 {r.chunk.chunk_id} | 頁 {r.chunk.source_page}]\n"
                f"{r.chunk.text}"
            )
    context = "\n\n---\n\n".join(context_parts)

    # ── Relations context (supervised attention knowledge) ─────────────────────
    retrieved_ids = {r.chunk.chunk_id for r in results}
    relation_lines: list[str] = []
    for rel in (relations or []):
        if rel.get("from_chunk_id") in retrieved_ids or rel.get("to_chunk_id") in retrieved_ids:
            # Prefer label names over raw text for readability
            from_name = rel.get("from_label") or (rel.get("from_text") or rel.get("from_chunk_id", "?"))[:40]
            to_name   = rel.get("to_label")   or (rel.get("to_text")   or rel.get("to_chunk_id",   "?"))[:40]
            edge_label = rel.get("label", "→")
            relation_lines.append(f"  「{from_name}」 --[{edge_label}]--> 「{to_name}」")

    relation_section = ""
    if relation_lines:
        relation_section = (
            "\n\n【已知圖譜關係】\n"
            + "\n".join(relation_lines)
            + "\n"
        )

    user_msg = f"上下文：\n{context}{relation_section}\n\n問題：{query}"

    if LLM_PROVIDER == "anthropic":
        return _anthropic_chat(SYSTEM_PROMPT, user_msg)
    return _ollama_chat(SYSTEM_PROMPT, user_msg)
