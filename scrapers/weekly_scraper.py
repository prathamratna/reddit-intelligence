"""
Weekly scraper: top posts of the week + top comments + cross-post patterns.
Runs via GitHub Actions every Sunday at 00:00 UTC.
Output: data/{category}/weekly/YYYY-MM-DD.json + data/{category}/latest_weekly.json
"""

import json
import sys
import os
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scrapers.reddit_client import get_top_posts, get_post_comments
from processors.cleaner import clean_post, clean_comment

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "subreddits.json")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def extract_patterns(posts: list[dict]) -> dict:
    words = Counter()
    high_ratio = [p for p in posts if p.get("upvote_ratio", 0) >= 0.9]
    controversial = [p for p in posts if p.get("upvote_ratio", 0) < 0.7]

    for post in posts:
        for word in post.get("title", "").lower().split():
            if len(word) > 4:
                words[word] += 1

    top_keywords = [w for w, _ in words.most_common(15) if w not in {"about", "with", "this", "that", "from", "have", "will", "your", "their", "been", "what", "when", "which"}]

    return {
        "top_keywords": top_keywords[:10],
        "high_consensus_posts": len(high_ratio),
        "controversial_posts": len(controversial),
        "avg_score": int(sum(p.get("score", 0) for p in posts) / max(len(posts), 1)),
        "most_discussed": sorted(posts, key=lambda x: x.get("num_comments", 0), reverse=True)[0].get("title") if posts else None,
        "highest_scored": sorted(posts, key=lambda x: x.get("score", 0), reverse=True)[0].get("title") if posts else None,
    }


def run():
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for category, meta in config["categories"].items():
        print(f"\n[{category.upper()}] Weekly scrape across {len(meta['subreddits'])} subreddits...")
        posts = []

        for subreddit in meta["subreddits"]:
            print(f"  -> r/{subreddit}")
            raw_posts = get_top_posts(subreddit, time_filter="week", limit=meta["weekly_limit"])

            for raw in raw_posts:
                post_data = raw.get("data", {})
                post_id = post_data.get("id", "")
                cleaned = clean_post(raw, include_comments=False)

                if not cleaned or cleaned.get("score", 0) < 20:
                    continue

                if post_data.get("num_comments", 0) > 5:
                    print(f"    +-- fetching comments for: {cleaned.get('title', '')[:60]}")
                    raw_comments = get_post_comments(subreddit, post_id, limit=meta["weekly_comments"])
                    cleaned["top_comments"] = [
                        c for c in [clean_comment(rc) for rc in raw_comments if rc.get("kind") == "t1"]
                        if c
                    ][:5]

                posts.append(cleaned)

        posts.sort(key=lambda x: x.get("score", 0), reverse=True)
        patterns = extract_patterns(posts)

        output = {
            "category": meta["label"],
            "type": "weekly",
            "week_ending": today,
            "total_posts": len(posts),
            "subreddits_scraped": [f"r/{s}" for s in meta["subreddits"]],
            "patterns": patterns,
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

        print(f"  OK {len(posts)} posts + patterns saved -> {date_file}")

    print("\n[DONE] Weekly scrape complete.")


if __name__ == "__main__":
    run()
