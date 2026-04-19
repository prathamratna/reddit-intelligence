"""
Daily scraper: top posts of the day via Composio Reddit API.
Runs via GitHub Actions every day at 00:00 UTC (05:30 IST).

Flow:
  1. Fetch top posts per subreddit (Composio SDK)
  2. Score + filter each post (scorer.py — zero Claude tokens)
  3. Save full JSON to data/ (permanent archive)
  4. Generate ultra-compressed digest (digest.py — ~500 tokens)
  5. Save digest to digests/daily/ (for GitHub Issue)
"""

import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scrapers.reddit_client import get_top_posts
from processors.cleaner import clean_post
from processors.scorer import score_post
from processors.digest import generate_daily_digest

CONFIG_PATH  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "subreddits.json")
DATA_DIR     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DIGEST_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "digests", "daily")


def run():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    category_posts_for_digest: dict = {}

    for category, meta in config["categories"].items():
        print(f"\n[{category.upper()}] Scraping {len(meta['subreddits'])} subreddits...")
        raw_posts = []

        for subreddit in meta["subreddits"]:
            print(f"  -> r/{subreddit}")
            posts = get_top_posts(subreddit, time_filter="day", limit=meta["daily_limit"])
            raw_posts.extend(posts)
            print(f"     {len(posts)} posts fetched")

        # Score + quality-filter — all logic in scorer.py, zero Claude tokens
        scored = []
        for post in raw_posts:
            result = score_post(post, category)
            if result:
                scored.append(clean_post(result))

        # Sort by engagement score (comments weighted 3x)
        scored.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

        # Top 5 per category goes into the digest
        top_posts = scored[:5]
        category_posts_for_digest[category] = top_posts

        # Save full scored data to permanent archive
        output = {
            "category":           meta["label"],
            "type":               "daily",
            "date":               today,
            "total_posts":        len(scored),
            "subreddits_scraped": [f"r/{s}" for s in meta["subreddits"]],
            "posts":              scored,
        }

        daily_dir   = os.path.join(DATA_DIR, category, "daily")
        latest_file = os.path.join(DATA_DIR, category, "latest_daily.json")
        os.makedirs(daily_dir, exist_ok=True)

        with open(os.path.join(daily_dir, f"{today}.json"), "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"  OK {len(scored)} posts passed quality gate -> saved")

    # Generate the ~500-token digest and save for GitHub Issue
    os.makedirs(DIGEST_DIR, exist_ok=True)
    digest_text  = generate_daily_digest(category_posts_for_digest, today)
    digest_file  = os.path.join(DIGEST_DIR, f"{today}.md")

    with open(digest_file, "w", encoding="utf-8") as f:
        f.write(digest_text)

    print(f"\n[DIGEST] Saved -> {digest_file}")
    print(f"[DIGEST] ~{len(digest_text.split()) * 1} words, ready for GitHub Issue")
    print("\n" + "=" * 60)
    print(digest_text)
    print("=" * 60)

    print("\n[DONE] Daily scrape complete.")


if __name__ == "__main__":
    run()
