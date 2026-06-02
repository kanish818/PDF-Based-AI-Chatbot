"""
LLM Service
Provides streaming chat completions via the Groq API using llama-3.3-70b-versatile.
"""

import logging
from typing import List, Dict, Any, Generator, Optional

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

_groq_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


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
    client = _get_client()
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
        stream = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            stream=True,
            temperature=0.3,
            max_tokens=2048,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as exc:
        logger.error("Groq streaming error: %s", exc)
        yield f"\n\n[Error generating response: {exc}]"
