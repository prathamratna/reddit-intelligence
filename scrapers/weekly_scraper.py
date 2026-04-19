"""
Weekly scraper: top posts of the week + comments + cross-post patterns.
Runs via GitHub Actions every Sunday at 01:00 UTC (06:30 IST).
Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET env vars.
"""

import json
import sys
import os
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scrapers.reddit_client import get_reddit, get_top_posts, get_post_comments
from processors.cleaner import clean_post, clean_comment

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "subreddits.json")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

STOPWORDS = {"about", "with", "this", "that", "from", "have", "will", "your", "their", "been", "what", "when", "which", "just", "there", "they", "been", "would", "could", "should"}


def extract_patterns(posts: list[dict]) -> dict:
    words = Counter()
    for post in posts:
        for word in post.get("title", "").lower().split():
            if len(word) > 4 and word not in STOPWORDS:
                words[word] += 1

    by_comments = sorted(posts, key=lambda x: x.get("num_comments", 0), reverse=True)
    by_score = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)

    return {
        "top_keywords": [w for w, _ in words.most_common(12)],
        "avg_score": int(sum(p.get("score", 0) for p in posts) / max(len(posts), 1)),
        "high_consensus": len([p for p in posts if p.get("upvote_ratio", 0) >= 0.92]),
        "controversial": len([p for p in posts if p.get("upvote_ratio", 0) < 0.65]),
        "most_discussed_title": by_comments[0].get("title") if by_comments else None,
        "most_discussed_url": by_comments[0].get("url") if by_comments else None,
        "highest_scored_title": by_score[0].get("title") if by_score else None,
        "highest_scored_url": by_score[0].get("url") if by_score else None,
    }


def run():
    reddit = get_reddit()
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for category, meta in config["categories"].items():
        print(f"\n[{category.upper()}] Weekly scrape across {len(meta['subreddits'])} subreddits...")
        posts = []

        for subreddit in meta["subreddits"]:
            print(f"  -> r/{subreddit}")
            raw_posts = get_top_posts(reddit, subreddit, time_filter="week", limit=meta["weekly_limit"])

            for post in raw_posts:
                if post.score < 20:
                    continue

                raw_comments = []
                if post.num_comments > 5:
                    print(f"    +-- comments: {post.title[:55]}")
                    raw_comments = get_post_comments(post, limit=meta["weekly_comments"])

                posts.append(clean_post(post, comments=raw_comments if raw_comments else None))

        posts.sort(key=lambda x: x.get("score", 0), reverse=True)

        output = {
            "category": meta["label"],
            "type": "weekly",
            "week_ending": today,
            "total_posts": len(posts),
            "subreddits_scraped": [f"r/{s}" for s in meta["subreddits"]],
            "patterns": extract_patterns(posts),
            "posts": posts,
        }

        weekly_dir = os.path.join(DATA_DIR, category, "weekly")
        os.makedirs(weekly_dir, exist_ok=True)

        date_file = os.path.join(weekly_dir, f"{today}.json")
        latest_file = os.path.join(DATA_DIR, category, "latest_weekly.json")

        with open(date_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"  OK {len(posts)} posts saved -> {date_file}")

    print("\n[DONE] Weekly scrape complete.")


if __name__ == "__main__":
    run()
