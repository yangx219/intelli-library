#!/usr/bin/env python3
"""
stdio MCP server: exposes Intelli Book Engine catalogue operations for Cursor / Claude Desktop.

Requires: pip install 'mcp>=1.27,<2'
Requires Django API reachable — default http://127.0.0.1:8000

Environment:
  IBE_API_BASE   Root URL of the running Django app (no trailing slash).

Configure MCP client with command:
  python scripts/mcp_intelli_book_server.py
(and cwd = repo root, same interpreter where `mcp` is installed).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

app = FastMCP("intelli-book-engine")


def _api_base() -> str:
    return os.environ.get("IBE_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _http_json(method: str, path_qs: str, payload: dict | None = None, timeout: int = 120) -> dict:
    url = _api_base() + path_qs
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        raw = json.dumps(payload).encode("utf-8")
        data = raw
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"http_error": e.code, "detail": err_body[:800]}
    except urllib.error.URLError as e:
        return {"error": "connection_failed", "detail": str(e.reason)}


@app.tool()
def catalogue_health() -> str:
    """Ping `/api/health`."""
    return json.dumps(_http_json("GET", "/api/health"))


@app.tool()
def catalogue_search(query: str, mode: str = "keywords", limit: int = 10) -> str:
    """Keyword/title/author/regex search against `/api/search`."""
    q = urllib.parse.quote(query)
    m = urllib.parse.quote(mode or "keywords")
    lim = max(1, min(int(limit), 20))
    path = f"/api/search?q={q}&mode={m}&order=default"
    data = _http_json("GET", path)
    return json.dumps(data, ensure_ascii=False)


@app.tool()
def catalogue_similar(query: str, limit: int = 8) -> str:
    """Similar editions via `/api/recommendations/query`."""
    q = urllib.parse.quote(query)
    lim = max(1, min(int(limit), 12))
    data = _http_json("GET", f"/api/recommendations/query?q={q}&limit={lim}")
    return json.dumps(data, ensure_ascii=False)


@app.tool()
def catalogue_stats() -> str:
    """Global index statistics."""
    return json.dumps(_http_json("GET", "/api/index/stats"))


@app.tool()
def ai_chat(
    messages_json: str,
    enable_tools: bool = True,
    inject_rag: bool = True,
) -> str:
    """
    Calls POST `/api/ai/chat` on the Django host.

    messages_json: JSON array like [{"role":"user","content":"Find sea poems"}]
    """
    try:
        parsed = json.loads(messages_json or "[]")
    except json.JSONDecodeError:
        return json.dumps({"error": "messages_json must be valid JSON"})
    payload = {
        "messages": parsed,
        "enable_tools": enable_tools,
        "inject_rag": inject_rag,
    }
    data = _http_json("POST", "/api/ai/chat", payload=payload, timeout=180)
    return json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    app.run()
