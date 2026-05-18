import json
import os
import time
from typing import Any

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from corpus.backend.ai_agent import build_rag_context_block, make_llm_client, run_agent_chat
from corpus.backend.rag_snippets import rag_block_for_book_ids
from corpus.backend.recommendations import RecommendationService
from corpus.backend.regex_search_service import RegexSearchService
from corpus.backend.search_service import SearchService
from corpus.cover_resolution import resolve_cover_url
from corpus.curated_classics import CURATED_CLASSICS, SAMPLE_FALLBACK
from corpus.models import Book, DocumentScore, IndexStat, Term


def _authors_from_book(authors_raw: str) -> list[str]:
    raw = (authors_raw or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


_NOISY_POPULAR_TITLE_FRAGMENTS: tuple[str, ...] = (
    # Periodicals & serials (dominate raw PageRank but are not “sit-down books”.)
    "magazine",
    "monthly",
    "quarterly",
    "weekly",
    "gazette",
    "newspaper",
    "serial",
    "atlantic monthly",
    "harper's new monthly",
    "international monthly",
    "catholic world",
    "published monthly",
    "published weekly",
    # Omnibus / collected blobs common on PG.
    "project gutenberg works",
    "complete works of",
    "complete essays",
    "complete collection",
    "century of ",
    " anthology",
    "anthology of ",
    # Volume numbering → usually multi-part serials.
    "vol.",
    "volume ",
    " no. ",
)


def _is_noisy_popular_catalogue_title(title: str) -> bool:
    """True for PG megablobs / magazines — hide from the Popular shelf."""
    t = (title or "").strip().lower()
    if not t:
        return True
    if len(t) > 140:
        return True
    return any(frag in t for frag in _NOISY_POPULAR_TITLE_FRAGMENTS)


def _sanitize_chat_messages(raw: Any, max_messages: int = 24) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw[-max_messages:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant", "system"):
            continue
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        if len(text) > 12000:
            text = text[:12000] + "…"
        out.append({"role": str(role), "content": text})
    return out


def _search_context_system_message(raw: Any) -> str | None:
    """
    Optional JSON from the SPA: current main-column search query + ordered hits
    so the concierge knows what the reader already sees.
    """
    if not isinstance(raw, dict):
        return None
    q = (raw.get("query") or "").strip()
    hits = raw.get("hits")
    if not isinstance(hits, list) or not hits:
        return None
    lines: list[str] = [
        "Current main-search results (already shown to the reader in the search column). Order matches the UI.",
    ]
    if q:
        lines.append(f"Search query: {q!r}")
    lines.append("Top hits:")
    n = 0
    for h in hits[:18]:
        if not isinstance(h, dict):
            continue
        bid = h.get("book_id")
        title = (h.get("title") or "").strip() or "(untitled)"
        auth_raw = h.get("authors")
        if isinstance(auth_raw, list):
            auth_s = ", ".join(str(x).strip() for x in auth_raw if x)
        else:
            auth_s = str(auth_raw or "").strip()
        n += 1
        frag = f"{n}. PG#{bid} — {title}" if bid is not None else f"{n}. {title}"
        if auth_s:
            frag += f" — {auth_s}"
        lines.append(frag)
    if n == 0:
        return None
    lines.append(
        "When the user asks about these results, their search results, 搜索结果, or what they see on the page, "
        "summarize and discuss this list first. Do not claim that no search has been run — the reader already searched in the main box."
    )
    return "\n".join(lines)


@require_GET
def api_root(request):
    return JsonResponse(
        {
            "service": "intelli-book-engine-api",
            "frontend": "Run the React app (see /frontend). API is under /api/.",
            "endpoints": {
                "health": "/api/health",
                "search": "/api/search",
                "recommendations": "/api/recommendations/query",
                "index_stats": "/api/index/stats",
                "catalog_popular": "/api/catalog/popular",
                "catalog_classics": "/api/catalog/classics",
                "ai_explain": "POST /api/ai/explain",
                "ai_chat": "POST /api/ai/chat",
            },
        }
    )


@require_GET
def health_view(request):
    return JsonResponse({"status": "ok"})


@require_GET
def index_stats_view(request):
    """Shape matches legacy SPA expectations (documents, avg_doc_length, terms, last_full_build)."""

    def stat_value(key: str) -> str | None:
        try:
            return IndexStat.objects.get(key=key).value
        except IndexStat.DoesNotExist:
            return None

    n_docs_raw = stat_value("N_docs")
    documents = int(n_docs_raw) if n_docs_raw and n_docs_raw.isdigit() else 0

    avg_raw = stat_value("avg_doc_len")
    avg_doc_length: float | None
    try:
        avg_doc_length = float(avg_raw) if avg_raw is not None else None
    except ValueError:
        avg_doc_length = None

    built = stat_value("built_at")

    return JsonResponse(
        {
            "documents": documents,
            "avg_doc_length": avg_doc_length,
            "terms": Term.objects.count(),
            "last_full_build": built,
        }
    )


@require_GET
def search_api(request):
    q = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "keywords")
    order = request.GET.get("order", "default")

    start = time.time()

    if mode == "regex":
        results = RegexSearchService.search(pattern=q, centrality=order, limit=20)
    elif mode == "title":
        results = SearchService.search_by_title(query=q, centrality=order, limit=20)
    elif mode == "author":
        results = SearchService.search_by_author(query=q, centrality=order, limit=20)
    else:
        results = SearchService.search(query=q, centrality=order, limit=20)

    base_url = "https://www.gutenberg.org/ebooks/"
    bids = [int(r["book_id"]) for r in results if r.get("book_id") is not None]
    books_by_id = {b.text_id: b for b in Book.objects.filter(text_id__in=bids)}
    for r in results:
        book_id = r.get("book_id")
        if book_id is not None:
            bid = int(book_id)
            r["gutenberg_url"] = f"{base_url}{bid}"
            r["cover_url"] = resolve_cover_url(bid, books_by_id.get(bid))

    elapsed = (time.time() - start) * 1000.0

    return JsonResponse(
        {
            "total": len(results),
            "elapsed_ms": elapsed,
            "results": results,
        }
    )


@require_GET
def recommendations_query_view(request):
    q = request.GET.get("q", "").strip()
    try:
        limit = int(request.GET.get("limit", 6))
    except ValueError:
        limit = 6
    limit = max(1, min(limit, 20))

    raw_results = RecommendationService.recommend_for_query(query=q, limit=limit)
    base_url = "https://www.gutenberg.org/ebooks/"

    bids = [int(r["book_id"]) for r in raw_results if r.get("book_id") is not None]
    books_by_id = {b.text_id: b for b in Book.objects.filter(text_id__in=bids)}

    items = []
    for r in raw_results:
        book_id = r.get("book_id")
        similarity = float(r.get("similarity", 0.0) or 0.0)
        bid = int(book_id) if book_id is not None else None
        book_row = books_by_id.get(bid) if bid is not None else None
        authors_list = _authors_from_book(r.get("authors") or "")
        items.append(
            {
                "book_id": book_id,
                "title": r.get("title"),
                "authors": authors_list,
                "reason": f"similarity: {similarity:.3f}",
                "gutenberg_url": f"{base_url}{book_id}" if book_id is not None else None,
                "cover_url": resolve_cover_url(bid, book_row) if bid is not None else None,
            }
        )

    return JsonResponse({"items": items})


@require_GET
def classic_books_view(request):
    """Fixed list of well-known Project Gutenberg editions (not tied to index PageRank)."""
    try:
        limit = int(request.GET.get("limit", 12))
    except ValueError:
        limit = 12
    limit = max(1, min(limit, 24))

    ebook_base = "https://www.gutenberg.org/ebooks/"
    seen: set[int] = set()
    items: list[dict[str, Any]] = []

    for bid, title, authors in CURATED_CLASSICS:
        if bid in seen:
            continue
        seen.add(bid)
        items.append(
            {
                "book_id": bid,
                "title": title,
                "authors": authors,
                "gutenberg_url": f"{ebook_base}{bid}",
                "cover_url": resolve_cover_url(bid, None),
            }
        )
        if len(items) >= limit:
            break

    bids = [it["book_id"] for it in items]
    book_rows = {b.text_id: b for b in Book.objects.filter(text_id__in=bids)}
    indexed_ids = set(book_rows.keys())
    for it in items:
        bid = it["book_id"]
        it["cover_url"] = resolve_cover_url(bid, book_rows.get(bid))
    for it in items:
        it["in_local_index"] = it["book_id"] in indexed_ids

    return JsonResponse({"items": items})


@require_GET
def popular_books_view(request):
    """Titles ranked by in-index PageRank, plus PG cover URLs. Falls back when the index has no scores."""
    try:
        limit = int(request.GET.get("limit", 12))
    except ValueError:
        limit = 12
    limit = max(1, min(limit, 24))

    raw_flag = (request.GET.get("raw") or "").strip().lower()
    skip_noise = raw_flag not in ("1", "true", "yes")

    ebook_base = "https://www.gutenberg.org/ebooks/"
    fallback = False
    items: list[dict[str, Any]] = []

    scan_cap = limit * 24 if skip_noise else limit
    scan_cap = max(scan_cap, limit)

    qs = (
        DocumentScore.objects.select_related("book")
        .exclude(book__title__exact="")
        .order_by("-pagerank", "-total")[:scan_cap]
    )

    for s in qs:
        if len(items) >= limit:
            break
        b = s.book
        title = (b.title or "").strip() or f"Book {b.text_id}"
        if skip_noise and _is_noisy_popular_catalogue_title(title):
            continue
        bid = int(b.text_id)
        items.append(
            {
                "book_id": bid,
                "title": title,
                "authors": _authors_from_book(b.authors),
                "gutenberg_url": f"{ebook_base}{bid}",
                "cover_url": resolve_cover_url(bid, b),
                "pagerank": float(s.pagerank),
            }
        )

    if not items:
        fallback = True
        for bid, title, authors in SAMPLE_FALLBACK[:limit]:
            items.append(
                {
                    "book_id": bid,
                    "title": title,
                    "authors": authors,
                    "gutenberg_url": f"{ebook_base}{bid}",
                    "cover_url": resolve_cover_url(bid, None),
                    "pagerank": None,
                }
            )

    return JsonResponse({"items": items, "fallback": fallback})


@csrf_exempt
@require_http_methods(["POST"])
def ai_explain_view(request) -> JsonResponse:
    """
    POST JSON:
      query (required),
      book_titles (optional list),
      book_ids (optional list[int]) — when local HTML paths exist, excerpts are injected for RAG.
    """
    try:
        body: dict[str, Any] = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    query = (body.get("query") or "").strip()
    book_titles = body.get("book_titles") or []
    raw_ids = body.get("book_ids")
    book_ids: list[int] = []
    if isinstance(raw_ids, list):
        for x in raw_ids:
            try:
                book_ids.append(int(x))
            except (TypeError, ValueError):
                continue

    if not query:
        return JsonResponse({"error": "query_required"}, status=400)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return JsonResponse(
            {
                "explanation": None,
                "detail": "Server has no OPENAI_API_KEY; add it to .env to enable this endpoint.",
            }
        )

    titles_text = "\n".join(f"- {t}" for t in book_titles[:12] if t)
    rag_block = rag_block_for_book_ids(query, book_ids) if book_ids else None
    rag_section = f"\n\nCorpus excerpts:\n{rag_block}" if rag_block else ""

    system = (
        "You help users understand book search results. "
        "Reply in the same language as the user's query when possible. "
        "Ground answers in the provided excerpts when present; if excerpts are missing, rely on titles only. "
        "Be concise (2–4 sentences)."
    )
    user_msg = (
        f"Search query: {query!r}\n"
        f"Top result titles from the catalogue:\n{titles_text or '(none)'}\n\n"
        "Briefly explain why these titles might match the query, and suggest how to refine the search."
        f"{rag_section}"
    )

    try:
        client = make_llm_client(api_key)
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=400,
            temperature=0.35,
        )
        explanation = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {"error": "upstream_failed", "detail": str(exc)},
            status=502,
        )

    return JsonResponse({"explanation": explanation, "rag_used": bool(rag_block)})


@csrf_exempt
@require_http_methods(["POST"])
def ai_chat_view(request) -> JsonResponse:
    """
    Conversational assistant with tool calling against the local index and optional corpus RAG.

    POST JSON:
      messages: [{ "role": "user"|"assistant"|"system", "content": "..." }],
      enable_tools: bool (default true),
      inject_rag: bool (default true) — adds excerpts from the last user turn via keyword search,
      search_context: optional { "query": str, "hits": [{ "book_id", "title", "authors?" }] } — main-column results,
      temperature: optional float.
    """
    try:
        body: dict[str, Any] = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    sanitized = _sanitize_chat_messages(body.get("messages"))
    if not sanitized:
        return JsonResponse({"error": "messages_required"}, status=400)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return JsonResponse(
            {
                "reply": None,
                "detail": "Server has no OPENAI_API_KEY; add it to .env to enable this endpoint.",
            }
        )

    enable_tools = body.get("enable_tools")
    if enable_tools is None:
        enable_tools = True
    inject_rag = body.get("inject_rag")
    if inject_rag is None:
        inject_rag = True

    temp_raw = body.get("temperature")
    try:
        temperature = float(temp_raw) if temp_raw is not None else 0.4
    except (TypeError, ValueError):
        temperature = 0.4

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    system_lines = [
        "You are a librarian assistant for a Project Gutenberg–indexed catalogue served by Intelli Book Engine.",
        "When fresh catalogue data is needed, call the provided tools instead of inventing titles.",
        "Keep replies concise unless the user asks for depth.",
        "If a system message titled 'Current main-search results' is present, the reader already ran search in the UI — "
        "use that list when they ask about search results or 搜索结果.",
    ]
    root_hint = getattr(settings, "CORPUS_ALLOWED_ROOT", "") or ""
    if root_hint.strip():
        system_lines.append(
            "Corpus HTML excerpts may appear in a separate system message; treat them as noisy OCR-adjacent text."
        )

    seed_for_rag = ""
    for msg in reversed(sanitized):
        if msg.get("role") == "user":
            seed_for_rag = msg.get("content") or ""
            break

    rag_block = build_rag_context_block(seed_for_rag, book_limit=5) if inject_rag and seed_for_rag else None

    page_search_block = _search_context_system_message(body.get("search_context"))

    llm_messages: list[dict[str, Any]] = [{"role": "system", "content": "\n".join(system_lines)}]
    if rag_block:
        llm_messages.append({"role": "system", "content": rag_block})
    if page_search_block:
        llm_messages.append({"role": "system", "content": page_search_block})
    llm_messages.extend(sanitized)

    try:
        reply, trace = run_agent_chat(
            llm_messages,
            model=model,
            api_key=api_key,
            enable_tools=bool(enable_tools),
            temperature=min(1.5, max(0.0, temperature)),
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {"error": "upstream_failed", "detail": str(exc)},
            status=502,
        )

    return JsonResponse(
        {
            "reply": reply,
            "tool_trace": trace,
            "rag_injected": bool(rag_block),
            "tools_enabled": bool(enable_tools),
        }
    )
