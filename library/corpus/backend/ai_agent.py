"""OpenAI chat with optional tool rounds — used by `/api/ai/chat`."""

from __future__ import annotations

import os
from typing import Any

from corpus.backend.ai_tools import TOOL_DEFINITIONS, execute_tool
from corpus.backend.rag_snippets import keywords_from_user_text, snippet_from_book
from corpus.backend.search_service import SearchService
from corpus.models import Book


def make_llm_client(api_key: str):
    """OpenAI SDK client; optional `OPENAI_BASE_URL` for DeepSeek and other compatible APIs."""
    from openai import OpenAI

    base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
    kw: dict[str, Any] = {"api_key": api_key}
    if base:
        kw["base_url"] = base
    return OpenAI(**kw)


def build_rag_context_block(seed_query: str, book_limit: int = 5) -> str | None:
    """Keyword search + local HTML excerpts for grounding."""
    q = seed_query.strip()
    if not q:
        return None
    hits = SearchService.search(q, centrality="default", limit=book_limit)
    if not hits:
        return None
    kws = keywords_from_user_text(q)
    ids = [int(h["book_id"]) for h in hits if h.get("book_id") is not None]
    books = Book.objects.filter(text_id__in=ids)
    book_map = {b.text_id: b for b in books}
    parts: list[str] = []
    for h in hits:
        bid = h.get("book_id")
        if bid is None:
            continue
        b = book_map.get(int(bid))
        if not b:
            continue
        title = h.get("title") or f"Book {bid}"
        snip = snippet_from_book(b, kws)
        excerpt = snip or "(No local HTML path — catalogue metadata only.)"
        parts.append(f"[pg:{bid}] {title}\n{excerpt}")
    if not parts:
        return None
    header = (
        "Grounding excerpts from your local corpus (Project Gutenberg HTML mirrors). "
        "Treat as noisy OCR-adjacent text; cite catalogue IDs only.\n\n"
    )
    return header + "\n\n---\n\n".join(parts)


def run_agent_chat(
    messages: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    enable_tools: bool,
    max_tool_rounds: int = 5,
    temperature: float = 0.4,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Returns assistant plain-text reply and a short trace of tool invocations.
    """
    client = make_llm_client(api_key)
    kwargs_tools: dict[str, Any] = {}
    if enable_tools:
        kwargs_tools = {"tools": TOOL_DEFINITIONS, "tool_choice": "auto"}

    msgs: list[dict[str, Any]] = list(messages)
    trace: list[dict[str, Any]] = []

    for _round in range(max_tool_rounds):
        resp = client.chat.completions.create(
            model=model,
            messages=msgs,
            temperature=temperature,
            **kwargs_tools,
        )
        choice = resp.choices[0].message
        tool_calls = choice.tool_calls
        if tool_calls:
            assistant_payload: dict[str, Any] = {
                "role": "assistant",
                "content": choice.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ],
            }
            msgs.append(assistant_payload)
            for tc in tool_calls:
                name = tc.function.name
                args = tc.function.arguments or "{}"
                out = execute_tool(name, args)
                trace.append(
                    {
                        "tool": name,
                        "round": _round,
                        "argument_chars": len(args),
                        "output_chars": len(out),
                    }
                )
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": out})
            continue

        text = (choice.content or "").strip()
        return text, trace

    return "The assistant stopped after the maximum number of tool rounds.", trace
