"""
Converts PRAW Submission/Comment objects to lean dicts (~80 tokens/post).
Every item includes a direct Reddit URL for citation.
"""

BASE = "https://www.reddit.com"


def clean_post(post, comments: list = None) -> dict:
    try:
        author = post.author.name if post.author else "[deleted]"
    except Exception:
        author = "[deleted]"

    out = {
        "id": post.id,
        "title": post.title.strip(),
        "subreddit": f"r/{post.subreddit.display_name}",
        "author": author,
        "score": post.score,
        "upvote_ratio": round(post.upvote_ratio, 2),
        "num_comments": post.num_comments,
        "url": f"{BASE}{post.permalink}",
        "flair": post.link_flair_text or None,
        "body": _truncate(post.selftext, 400) if post.is_self else None,
        "external_url": post.url if not post.is_self else None,
        "created_utc": int(post.created_utc),
    }

    if comments:
        out["top_comments"] = [c for c in [clean_comment(c) for c in comments] if c][:5]

    return {k: v for k, v in out.items() if v is not None and v != ""}


def clean_comment(comment) -> dict:
    try:
        if not hasattr(comment, "body") or comment.body in ("[deleted]", "[removed]"):
            return {}
        author = comment.author.name if comment.author else "[deleted]"
        return {
            "author": author,
            "score": comment.score,
            "body": _truncate(comment.body, 300),
            "url": f"{BASE}{comment.permalink}",
        }
    except Exception:
        return {}


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n\n", " ").replace("\n", " ")
    return text[:max_chars] + "..." if len(text) > max_chars else text
