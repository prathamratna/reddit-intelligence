"""
Reddit client — direct calls to Reddit's public JSON API.
No auth. No secrets. No SDK. No Composio. Works anywhere.

Endpoints:
  Top posts:   GET https://www.reddit.com/r/{sub}/top.json?t={t}&limit={n}
  Search:      GET https://www.reddit.com/search.json?q={q}&sort={sort}&limit={n}
  Comments:    GET https://www.reddit.com/comments/{id}.json?limit={n}&depth=1

Rate limit: Reddit allows ~60 req/min unauthenticated. Our 1.5-2.5s throttle
keeps us at ~0.5 req/s — well within limits. User-Agent is required.
"""

import sys
import time
import random

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL   = "https://www.reddit.com"
_USER_AGENT = "reddit-intelligence-bot/2.0 by prathamratna"

_MAX_RETRIES     = 3
_RETRY_BASE_SECS = 5
_TIMEOUT         = 20


# ---------------------------------------------------------------------------
# Core HTTP caller
# ---------------------------------------------------------------------------

def _get(url: str, params: dict) -> dict:
    """GET a Reddit JSON endpoint with retry on transient errors."""
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept":     "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=_TIMEOUT,
                             follow_redirects=True)

            if resp.status_code == 200:
                return resp.json()

            # Rate-limited or server error — back off and retry
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {resp.status_code}")

            # Non-retryable (403 private sub, 404 not found …)
            resp.raise_for_status()

        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SECS * (2 ** (attempt - 1))   # 5s, 10s
                print(f"  [RETRY {attempt}/{_MAX_RETRIES}] {url} → {e} — retrying in {wait}s",
                      file=sys.stderr)
                time.sleep(wait)

    raise last_exc  # type: ignore[misc]


def _throttle():
    """Polite delay between calls to stay within Reddit rate limits."""
    time.sleep(random.uniform(1.5, 2.5))


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def _parse_listing(data: dict, fallback_sub: str | None) -> list[dict]:
    """
    Parse a Reddit Listing response into a flat list of post dicts.
    Shape: data → data → children[]
    """
    try:
        listing = (data or {}).get("data", {})
        posts = []
        for child in listing.get("children") or []:
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


def _parse_comments(data: list, limit: int = 5) -> list[str]:
    """
    Extract top-level comment bodies from a /comments/{id}.json response.
    Reddit returns a 2-element list: [post_listing, comments_listing].
    """
    try:
        comments_listing = data[1] if len(data) > 1 else {}
        children = (comments_listing.get("data") or {}).get("children") or []
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
        data = _get(
            f"{_BASE_URL}/r/{subreddit}/top.json",
            {"t": time_filter, "limit": limit, "raw_json": 1},
        )
        return _parse_listing(data, subreddit)
    except Exception as e:
        print(f"[ERROR] get_top_posts r/{subreddit}: {e}", file=sys.stderr)
        return []


def search_posts(query: str, limit: int = 25, sort: str = "top") -> list[dict]:
    """Search Reddit across all subreddits for a keyword query."""
    _throttle()
    try:
        data = _get(
            f"{_BASE_URL}/search.json",
            {"q": query, "sort": sort, "limit": limit, "t": "week", "raw_json": 1},
        )
        return _parse_listing(data, fallback_sub=None)
    except Exception as e:
        print(f"[ERROR] search '{query}': {e}", file=sys.stderr)
        return []


def get_post_comments(article_id: str, limit: int = 5) -> list[str]:
    """Fetch top comments for a post by its base-36 article ID."""
    _throttle()
    try:
        data = _get(
            f"{_BASE_URL}/comments/{article_id}.json",
            {"limit": limit, "depth": 1, "raw_json": 1},
        )
        return _parse_comments(data, limit)
    except Exception as e:
        print(f"[ERROR] comments for {article_id}: {e}", file=sys.stderr)
        return []
