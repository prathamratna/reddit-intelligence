"""
Weekly scraper: deep research via Composio Reddit API.
Runs via GitHub Actions at 01:00 UTC Sundays (06:30 IST).

Flow:
  1. Top posts of the week per subreddit (scored + filtered)
  2. Top comments fetched for high-engagement posts
  3. Targeted search queries from research_plan.json (intent-rich signal)
  4. Generate weekly digest (~1,200 tokens) for GitHub Issue
"""

import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scrapers.reddit_client import get_top_posts, search_posts, get_post_comments
from processors.cleaner import clean_post
from processors.scorer import score_post
from processors.digest import generate_weekly_digest

CONFIG_PATH        = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "subreddits.json")
RESEARCH_PLAN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "research_plan.json")
DATA_DIR           = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DIGEST_DIR         = os.path.join(os.path.dirname(os.path.dirname(__file__)), "digests", "weekly")

# Pull comments only for posts above this engagement score — avoids wasting API calls
COMMENTS_ENGAGEMENT_THRESHOLD = 150


def run():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    with open(RESEARCH_PLAN_PATH, encoding="utf-8") as f:
        research_plan = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    category_posts: dict = {}
    search_results: dict = {}

    # -------------------------------------------------------------------------
    # Part 1: Top posts of the week per subreddit
    # -------------------------------------------------------------------------
    for category, meta in config["categories"].items():
        print(f"\n[{category.upper()}] Weekly top posts...")
        raw_posts = []

        for subreddit in meta["subreddits"]:
            print(f"  -> r/{subreddit}")
            posts = get_top_posts(subreddit, time_filter="week", limit=meta["weekly_limit"])
            raw_posts.extend(posts)
            print(f"     {len(posts)} fetched")

        # Score + filter — all logic in scorer.py, zero Claude tokens
        scored = []
        for post in raw_posts:
            result = score_post(post, category)
            if result:
                # Pull top comments for high-engagement posts only
                eng = result.get("engagement_score", 0)
                if eng >= COMMENTS_ENGAGEMENT_THRESHOLD and post.get("id"):
                    print(f"    -> Comments for: {post['title'][:55]}...")
                    result["comments"] = get_post_comments(post["id"], limit=3)
                scored.append(clean_post(result))

        scored.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
        category_posts[category] = scored[:5]

        # Save to permanent archive
        weekly_dir  = os.path.join(DATA_DIR, category, "weekly")
        latest_file = os.path.join(DATA_DIR, category, "latest_weekly.json")
        os.makedirs(weekly_dir, exist_ok=True)

        output = {
            "category":    meta["label"],
            "type":        "weekly",
            "week_ending": today,
            "total_posts": len(scored),
            "posts":       scored,
        }
        with open(os.path.join(weekly_dir, f"{today}.json"), "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"  OK {len(scored)} posts passed gate -> saved")

    # -------------------------------------------------------------------------
    # Part 2: Search intelligence from research_plan.json
    # Finds intent-rich discussions that don't always rank as top posts.
    # -------------------------------------------------------------------------
    print("\n[SEARCH] Running targeted queries from research_plan.json...")

    for category, plan in research_plan.items():
        queries   = plan.get("search_queries", [])
        min_score = plan.get("min_score_search", 10)
        search_results[category] = {}

        print(f"\n  [{category.upper()}] {len(queries)} queries")
        for query in queries:
            print(f"    -> '{query}'")
            results  = search_posts(query, limit=10, sort="top")
            filtered = [r for r in results if r.get("score", 0) >= min_score]
            filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
            top2 = filtered[:2]

            if top2:
                search_results[category][query] = top2
                print(f"       {len(top2)} results kept (score >= {min_score})")
            else:
                print(f"       0 results above threshold")

    # -------------------------------------------------------------------------
    # Generate digest
    # -------------------------------------------------------------------------
    os.makedirs(DIGEST_DIR, exist_ok=True)
    digest_text = generate_weekly_digest(category_posts, search_results, today)
    digest_file = os.path.join(DIGEST_DIR, f"{today}.md")

    with open(digest_file, "w", encoding="utf-8") as f:
        f.write(digest_text)

    print(f"\n[DIGEST] Saved -> {digest_file}")
    print("\n" + "=" * 60)
    print(digest_text)
    print("=" * 60)

    print("\n[DONE] Weekly research complete.")


if __name__ == "__main__":
    run()
