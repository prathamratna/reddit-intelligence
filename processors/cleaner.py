"""
Strips Reddit's verbose JSON (~500 tokens/post) down to ~80 tokens/post.
Keeps everything needed for Claude analysis + full citations.
"""

BASE_URL = "https://www.reddit.com"


def clean_post(raw: dict, include_comments: bool = False, raw_comments: list = None) -> dict:
    d = raw.get("data", {})
    if not d:
        return {}

    post_id = d.get("id", "")
    subreddit = d.get("subreddit", "")
    permalink = d.get("permalink", "")

    post = {
        "id": post_id,
        "title": d.get("title", "").strip(),
        "subreddit": f"r/{subreddit}",
        "author": d.get("author", "[deleted]"),
        "score": d.get("score", 0),
        "upvote_ratio": d.get("upvote_ratio", 0),
        "num_comments": d.get("num_comments", 0),
        "url": f"{BASE_URL}{permalink}",
        "external_url": d.get("url", "") if not d.get("is_self") else None,
        "body": _truncate(d.get("selftext", ""), 400),
        "flair": d.get("link_flair_text", None),
        "created_utc": int(d.get("created_utc", 0)),
    }

    if include_comments and raw_comments:
        post["top_comments"] = [clean_comment(c) for c in raw_comments if c.get("kind") == "t1"][:5]

    return {k: v for k, v in post.items() if v is not None and v != ""}


def clean_comment(raw: dict) -> dict:
    d = raw.get("data", {})
    if not d or d.get("body") in ("[deleted]", "[removed]", None):
        return {}

    permalink = d.get("permalink", "")
    return {
        "author": d.get("author", "[deleted]"),
        "score": d.get("score", 0),
        "body": _truncate(d.get("body", ""), 300),
        "url": f"{BASE_URL}{permalink}" if permalink else None,
    }


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n\n", " ").replace("\n", " ")
    return text[:max_chars] + "..." if len(text) > max_chars else text
