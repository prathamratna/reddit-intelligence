import praw
import os
import sys


def get_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent="reddit-intelligence/1.0 (open-source research tool)",
    )


def get_top_posts(reddit: praw.Reddit, subreddit: str, time_filter: str = "day", limit: int = 10):
    try:
        return list(reddit.subreddit(subreddit).top(time_filter=time_filter, limit=limit))
    except Exception as e:
        print(f"[ERROR] r/{subreddit}: {e}", file=sys.stderr)
        return []


def get_post_comments(post, limit: int = 5) -> list:
    try:
        post.comments.replace_more(limit=0)
        return post.comments.list()[:limit]
    except Exception as e:
        print(f"[ERROR] comments for {post.id}: {e}", file=sys.stderr)
        return []
