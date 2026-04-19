"""
Cleaner — strips junk fields, caps selftext, normalizes structure.
Only keeps fields that matter for the digest and Claude context.
~30 tokens per post after cleaning vs ~300 for raw data.
"""

_KEEP_FIELDS = {
    "id", "title", "subreddit", "author", "score", "num_comments",
    "url", "permalink", "created_utc", "is_self", "selftext",
    "content_type", "engagement_score", "linkedin_angle", "comments",
}


def clean_post(raw: dict) -> dict:
    cleaned = {
        k: v for k, v in raw.items()
        if k in _KEEP_FIELDS and v is not None and v != "" and v != []
    }
    # Cap selftext at 300 chars — enough context, not a token drain
    if "selftext" in cleaned and len(cleaned["selftext"]) > 300:
        cleaned["selftext"] = cleaned["selftext"][:300].rstrip() + "…"
    return cleaned
