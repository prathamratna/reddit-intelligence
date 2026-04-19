"""
Daily scraper: top posts of the day, no comments.
Runs via GitHub Actions every day at 05:30 IST (00:00 UTC).
Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET env vars.
"""

import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scrapers.reddit_client import get_reddit, get_top_posts
from processors.cleaner import clean_post

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "subreddits.json")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def run():
    reddit = get_reddit()
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for category, meta in config["categories"].items():
        print(f"\n[{category.upper()}] Scraping {len(meta['subreddits'])} subreddits...")
        posts = []

        for subreddit in meta["subreddits"]:
            print(f"  -> r/{subreddit}")
            raw_posts = get_top_posts(reddit, subreddit, time_filter="day", limit=meta["daily_limit"])
            for post in raw_posts:
                if post.score >= 10:
                    posts.append(clean_post(post))

        posts.sort(key=lambda x: x.get("score", 0), reverse=True)

        output = {
            "category": meta["label"],
            "type": "daily",
            "date": today,
            "total_posts": len(posts),
            "subreddits_scraped": [f"r/{s}" for s in meta["subreddits"]],
            "posts": posts,
        }

        daily_dir = os.path.join(DATA_DIR, category, "daily")
        os.makedirs(daily_dir, exist_ok=True)

        date_file = os.path.join(daily_dir, f"{today}.json")
        latest_file = os.path.join(DATA_DIR, category, "latest_daily.json")

        with open(date_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"  OK {len(posts)} posts saved -> {date_file}")

    print("\n[DONE] Daily scrape complete.")


if __name__ == "__main__":
    run()
