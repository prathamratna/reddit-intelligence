"""
Reddit client via Composio SDK.
No raw RSS, no PRAW, no IP blocks — Composio handles OAuth.
Requires: COMPOSIO_API_KEY environment variable.

Key design decisions:
- Single toolset instance (no repeated cache-refresh spam)
- connected_account_id="reddit_carid-smit" passed per-call (bypasses entity lookup)
- Entity lookup (entity_id) is intentionally NOT used — it caused HTTP 500 on every call
  because "carid-smit" is a connection name, not a Composio entity ID
"""

import os
import sys
import time
import random

from composio import ComposioToolSet

# The confirmed connection ID from app.composio.dev → Reddit → Connected Accounts
_REDDIT_CONNECTION_ID = "reddit_carid-smit"

# Single toolset instance — avoids repeated SDK init and cache-refresh churn
_TOOLSET_INSTANCE: ComposioToolSet | None = None

# Retry config for transient errors
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 3


def _toolset() -> ComposioToolSet:
    global _TOOLSET_INSTANCE
    if _TOOLSET_INSTANCE is None:
        api_key = os.environ.get("COMPOSIO_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "COMPOSIO_API_KEY not set. Add it as a GitHub secret or local env var.\n"
                "Get it from: app.composio.dev → Settings → API Keys"
            )
        # No entity_id — we pass connected_account_id per-call instead
        _TOOLSET_INSTANCE = ComposioToolSet(api_key=api_key)
    return _TOOLSET_INSTANCE


def _execute(action: str, params: dict) -> dict:
    """
    Execute a Composio action with connected_account_id and automatic retry.
    Passing connected_account_id directly skips entity-lookup (which caused HTTP 500).
    """
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = _toolset().execute_action(
                action=action,
                params=params,
                connected_account_id=_REDDIT_CONNECTION_ID,
            )
            # SDK returns {successfull: False, error: "..."} after exhausting its retries
            # Note: Composio SDK typos "successfull" with double-l
            if isinstance(result, dict) and (
                result.get("successfull") is False
                or result.get("successful") is False
            ):
                error_msg = result.get("error") or "Composio returned failure"
                raise RuntimeError(error_msg)
            return result
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SECONDS * (2 ** (attempt - 1))  # 3s, 6s
                print(
                    f"  [RETRY {attempt}/{_MAX_RETRIES}] {action} → {e} — retrying in {wait}s",
                    file=sys.stderr,
                )
                time.sleep(wait)

    raise last_exc


def _throttle():
    """Polite delay between subreddit calls to stay within rate limits."""
    time.sleep(random.uniform(1.5, 2.5))


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def _parse_listing(result: dict, fallback_subreddit: str | None) -> list[dict]:
    """
    Navigate Composio's nested response structure to extract post dicts.
    Composio wraps Reddit's response: result → data → data → children
    """
    try:
        data = (result or {}).get("data", {})
        if isinstance(data.get("data"), dict):
            data = data["data"]
        children = data.get("children") or []
        posts = []
        for child in children:
            if child.get("kind") != "t3":
                continue
            d = child.get("data") or {}
            permalink = d.get("permalink", "")
            posts.append({
                "id":           d.get("id", ""),
                "title":        (d.get("title") or "").strip(),
                "subreddit":    f"r/{d.get('subreddit') or fallback_subreddit or 'unknown'}",
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
        comments_listing = data.get("comments_listing", {})
        children = ((comments_listing.get("data") or {}).get("children") or [])
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
        result = _execute(
            action="REDDIT_GET_R_TOP",
            params={"subreddit": subreddit, "t": time_filter, "limit": limit},
        )
        return _parse_listing(result, subreddit)
    except Exception as e:
        print(f"[ERROR] get_top_posts r/{subreddit}: {e}", file=sys.stderr)
        return []


def search_posts(query: str, limit: int = 25, sort: str = "top") -> list[dict]:
    """Search Reddit across all subreddits for a keyword query."""
    _throttle()
    try:
        result = _execute(
            action="REDDIT_SEARCH_ACROSS_SUBREDDITS",
            params={"search_query": query, "limit": limit, "sort": sort},
        )
        return _parse_listing(result, fallback_subreddit=None)
    except Exception as e:
        print(f"[ERROR] search '{query}': {e}", file=sys.stderr)
        return []


def get_post_comments(article_id: str, limit: int = 5) -> list[str]:
    """Fetch top comments for a post by its base-36 article ID."""
    _throttle()
    try:
        result = _execute(
            action="REDDIT_RETRIEVE_POST_COMMENTS",
            params={"article": article_id},
        )
        return _parse_comments(result, limit)
    except Exception as e:
        print(f"[ERROR] comments for {article_id}: {e}", file=sys.stderr)
        return []
