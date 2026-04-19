import httpx
import time
import random
import sys

BASE_URL = "https://www.reddit.com"
HEADERS = {
    "User-Agent": "reddit-intelligence/1.0 (open-source research tool; github.com/pratham)"
}


def _fetch(url: str, params: dict = None) -> dict:
    time.sleep(random.uniform(2.0, 4.0))  # Reddit .json rate limit: ~10 req/min
    try:
        response = httpx.get(url, headers=HEADERS, params=params, timeout=30, follow_redirects=True)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] {url} → HTTP {e.response.status_code}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"[ERROR] {url} → {e}", file=sys.stderr)
        return {}


def get_top_posts(subreddit: str, time_filter: str = "day", limit: int = 10) -> list[dict]:
    url = f"{BASE_URL}/r/{subreddit}/top.json"
    data = _fetch(url, params={"t": time_filter, "limit": limit})
    return data.get("data", {}).get("children", [])


def get_post_comments(subreddit: str, post_id: str, limit: int = 5) -> list[dict]:
    url = f"{BASE_URL}/r/{subreddit}/comments/{post_id}.json"
    data = _fetch(url, params={"limit": limit, "depth": 2, "sort": "top"})
    if not data or not isinstance(data, list) or len(data) < 2:
        return []
    return data[1].get("data", {}).get("children", [])


def get_subreddit_info(subreddit: str) -> dict:
    url = f"{BASE_URL}/r/{subreddit}/about.json"
    data = _fetch(url)
    return data.get("data", {})
