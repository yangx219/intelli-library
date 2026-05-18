"""OpenAI tool schemas and server-side execution against the local search index."""

from __future__ import annotations

import json
from typing import Any

from corpus.backend.recommendations import RecommendationService
from corpus.backend.regex_search_service import RegexSearchService
from corpus.backend.search_service import SearchService

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": (
                "Full-text / TF-IDF catalogue search (keywords), or narrow modes title, author, regex. "
                "Returns book_id, title, authors, scores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User query string"},
                    "mode": {
                        "type": "string",
                        "enum": ["keywords", "title", "author", "regex"],
                        "description": "Search mode",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max hits (1–20)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "similar_books_for_query",
            "description": (
                "Titles similar to a natural-language seed query using the document similarity graph / vectors."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "1–12 recommendations"},
                },
                "required": ["query"],
            },
        },
    },
]


def _truncate_json(data: Any, max_chars: int = 12000) -> str:
    s = json.dumps(data, ensure_ascii=False)
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n…(truncated)…"


def execute_tool(name: str, arguments_json: str) -> str:
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid_arguments_json"})

    if name == "search_catalog":
        q = str(args.get("query") or "").strip()
        if not q:
            return json.dumps({"error": "query_required"})
        mode = str(args.get("mode") or "keywords")
        try:
            limit = int(args.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 20))

        if mode == "regex":
            rows = RegexSearchService.search(pattern=q, centrality="default", limit=limit)
        elif mode == "title":
            rows = SearchService.search_by_title(query=q, centrality="default", limit=limit)
        elif mode == "author":
            rows = SearchService.search_by_author(query=q, centrality="default", limit=limit)
        else:
            rows = SearchService.search(query=q, centrality="default", limit=limit)

        slim = [
            {
                "book_id": r.get("book_id"),
                "title": r.get("title"),
                "authors": r.get("authors"),
                "score": r.get("score"),
                "match_terms": (r.get("match_terms") or [])[:24],
            }
            for r in rows[:limit]
        ]
        return _truncate_json({"hits": slim})

    if name == "similar_books_for_query":
        q = str(args.get("query") or "").strip()
        if not q:
            return json.dumps({"error": "query_required"})
        try:
            lim = int(args.get("limit") or 6)
        except (TypeError, ValueError):
            lim = 6
        lim = max(1, min(lim, 12))
        raw = RecommendationService.recommend_for_query(query=q, limit=lim)
        slim = [
            {
                "book_id": r.get("book_id"),
                "title": r.get("title"),
                "similarity": float(r.get("similarity") or 0.0),
            }
            for r in raw
        ]
        return _truncate_json({"items": slim})

    return json.dumps({"error": "unknown_tool", "name": name})
