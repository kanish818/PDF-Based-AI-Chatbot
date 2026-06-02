"""
LLM Service
Provides streaming chat completions via the Groq API using llama-3.3-70b-versatile.
"""

import json
import logging
from typing import List, Dict, Any, Generator, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


SYSTEM_PROMPT_TEMPLATE = """\
You are a PDF question-answering assistant.

Answer ONLY from the provided document excerpts.
Use only the selected document excerpts shown below. Never mix in other PDFs or outside knowledge.
If the excerpts do not contain enough evidence, say:
"I could not find this information in the selected document(s)."

Response rules:
- Be concise and factual.
- When answering, cite the supporting source inline as [filename, Page X].
- If multiple documents are present, clearly separate which document each point comes from.
- Do not claim anything that is not directly supported by the excerpts.
- For summaries, summarise only what is present in the excerpts.
- Treat prior chat history as conversational context only. If history conflicts with the current excerpts, ignore the history and rely on the excerpts.

--- DOCUMENT EXCERPTS ---
{context}
--- END OF EXCERPTS ---
"""


def _build_context(context_chunks: List[Dict[str, Any]]) -> str:
    """Format retrieval results into a readable context block."""
    if not context_chunks:
        return "No relevant document excerpts found."

    parts: List[str] = []
    for chunk in context_chunks:
        filename = chunk.get("filename", "unknown")
        page_num = chunk.get("page_num", "?")
        text = chunk.get("text", "").strip()
        parts.append(
            f"Filename: {filename}\n"
            f"Page: {page_num}\n"
            f"Excerpt:\n{text}"
        )

    return "\n\n".join(parts)


def stream_chat(
    question: str,
    context_chunks: List[Dict[str, Any]],
    chat_history: List[Dict[str, str]],
) -> Generator[str, None, None]:
    """
    Stream a chat completion from Groq.

    Args:
        question:      The user's current question.
        context_chunks: Retrieved document chunks for RAG context.
        chat_history:  Previous messages [{role, content}, ...].

    Yields:
        Incremental text chunks from the model.
    """
    context = _build_context(context_chunks)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)

    # Build message array: system + history + current question
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    logger.info(
        "Streaming Groq completion. history_len=%d, context_chunks=%d",
        len(chat_history),
        len(context_chunks),
    )

    try:
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "stream": True,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            with client.stream("POST", GROQ_URL, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning("Skipping malformed Groq stream payload: %s", data)
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
    except Exception as exc:
        logger.error("Groq streaming error: %s", exc)
        yield f"\n\n[Error generating response: {exc}]"
