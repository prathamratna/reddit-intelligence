"""
Reddit client — direct HTTP calls to Composio REST API.
No SDK. No cache refresh. No entity lookup. No 500s from metadata calls.

Endpoint: POST https://backend.composio.dev/api/v2/actions/{ACTION}/execute
Auth:      x-api-key header
Body:      { connectedAccountId, entityId, appName, input }

This bypasses all composio-core SDK overhead that was causing HTTP 500 on
every call due to failed action-schema cache refreshes and entity lookups.
"""

import os
import sys
import time
import random

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL        = "https://backend.composio.dev/api/v2/actions"
_CONNECTION_ID   = "reddit_carid-smit"   # from app.composio.dev → Reddit → Connected Accounts
_APP_NAME        = "reddit"

_MAX_RETRIES     = 3
_RETRY_BASE_SECS = 3
_TIMEOUT         = 30


# ---------------------------------------------------------------------------
# Core HTTP caller
# ---------------------------------------------------------------------------

def _api_key() -> str:
    key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "COMPOSIO_API_KEY not set.\n"
            "Get it from: app.composio.dev → Settings → API Keys\n"
            "Add it as a GitHub secret named COMPOSIO_API_KEY."
        )
    return key


def _execute(action: str, params: dict) -> dict:
    """
    POST to Composio execute endpoint with retry.
    Skips SDK entirely — no cache refresh, no entity lookup.
    """
    url = f"{_BASE_URL}/{action}/execute"
    headers = {
        "x-api-key":     _api_key(),
        "Content-Type":  "application/json",
    }
    body = {
        "connectedAccountId": _CONNECTION_ID,
        "entityId":           "default",
        "appName":            _APP_NAME,
        "input":              params,
        "text":               None,
        "authConfig":         None,
        "sessionInfo":        {"sessionId": None},
        "allowTracing":       False,
    }

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = httpx.post(url, headers=headers, json=body, timeout=_TIMEOUT)

            if resp.status_code == 200:
                data = resp.json()
                # Composio wraps errors inside a 200 with successfull=False
                if isinstance(data, dict) and data.get("successfull") is False:
                    raise RuntimeError(data.get("error") or "Composio returned failure")
                return data

            # Retryable server errors
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

            # Non-retryable (401, 403, 404 …)
            resp.raise_for_status()

        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SECS * (2 ** (attempt - 1))  # 3s, 6s
                print(f"  [RETRY {attempt}/{_MAX_RETRIES}] {action} → {e} — retrying in {wait}s",
                      file=sys.stderr)
                time.sleep(wait)

    raise last_exc  # type: ignore[misc]


def _throttle():
    """Polite delay between calls to stay within Reddit rate limits."""
    time.sleep(random.uniform(1.5, 2.5))


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def _parse_listing(result: dict, fallback_sub: str | None) -> list[dict]:
    """
    Navigate Composio's nested Reddit response to extract post dicts.
    Shape: result → data → (data →) children[]
    """
    try:
        data = (result or {}).get("data", {})
        if isinstance(data.get("data"), dict):
            data = data["data"]
        posts = []
        for child in data.get("children") or []:
            if child.get("kind") != "t3":
                continue
            d = child.get("data") or {}
            permalink = d.get("permalink", "")
            posts.append({
                "id":           d.get("id", ""),
                "title":        (d.get("title") or "").strip(),
                "subreddit":    f"r/{d.get('subreddit') or fallback_sub or 'unknown'}",
                "author":       d.get("author") or "[unknown]",
                "score":        int(d.get("score") or 0),
                "num_comments": int(d.get("num_comments") or 0),
                "url":          d.get("url") or f"https://reddit.com{permalink}",
                "permalink":    f"https://reddit.com{permalink}",
                "created_utc":  int(d.get("created_utc") or 0),
                "is_self":      bool(d.get("is_self", False)),
                "selftext":     (d.get("selftext") or "")[:500],
            })
        return posts
    except Exception as e:
        print(f"[ERROR] _parse_listing: {e}", file=sys.stderr)
        return []


def _parse_comments(result: dict, limit: int = 5) -> list[str]:
    """Extract top-level comment bodies from a post comments response."""
    try:
        data = (result or {}).get("data", {})
        children = ((data.get("comments_listing") or {})
                    .get("data", {})
                    .get("children") or [])
        out = []
        for child in children:
            if child.get("kind") != "t1":
                continue
            body = ((child.get("data") or {}).get("body") or "").strip()
            if body and body not in ("[deleted]", "[removed]") and len(body) > 15:
                out.append(body[:200])
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        print(f"[ERROR] _parse_comments: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_top_posts(subreddit: str, time_filter: str = "day", limit: int = 10) -> list[dict]:
    """Fetch top posts from a subreddit for a given time window."""
    _throttle()
    try:
        result = _execute("REDDIT_GET_R_TOP",
                          {"subreddit": subreddit, "t": time_filter, "limit": limit})
        return _parse_listing(result, subreddit)
    except Exception as e:
        print(f"[ERROR] get_top_posts r/{subreddit}: {e}", file=sys.stderr)
        return []


def search_posts(query: str, limit: int = 25, sort: str = "top") -> list[dict]:
    """Search Reddit across all subreddits for a keyword query."""
    _throttle()
    try:
        result = _execute("REDDIT_SEARCH_ACROSS_SUBREDDITS",
                          {"search_query": query, "limit": limit, "sort": sort})
        return _parse_listing(result, fallback_sub=None)
    except Exception as e:
        print(f"[ERROR] search '{query}': {e}", file=sys.stderr)
        return []


def get_post_comments(article_id: str, limit: int = 5) -> list[str]:
    """Fetch top comments for a post by its base-36 article ID."""
    _throttle()
    try:
        result = _execute("REDDIT_RETRIEVE_POST_COMMENTS", {"article": article_id})
        return _parse_comments(result, limit)
    except Exception as e:
        print(f"[ERROR] comments for {article_id}: {e}", file=sys.stderr)
        return []
