# reddit-intelligence

Automated Reddit research pipeline for LinkedIn content. Runs free on GitHub Actions — no servers, no infra.

Every morning at **05:30 IST** a GitHub Issue lands in your inbox with the day's top Reddit signal across AI, personal branding, VC/funding, and cybersecurity — pre-scored, pre-filtered, and pre-framed with LinkedIn angles. No manual scrolling. No noise.

---

## How it works

```
GitHub Actions (cron)
  → Composio Reddit API     (real upvote scores, no IP blocks)
  → processors/scorer.py   (engagement formula + content type + LinkedIn angle)
  → processors/digest.py   (compresses to ~500 tokens — zero noise)
  → GitHub Issue            (lands in your inbox automatically)
```

All intelligence runs as pure Python before Claude ever sees a token. Claude's job is creation only.

### Engagement scoring

```
engagement_score = (upvotes × 1.0) + (comments × 3.0)
```

Comments are weighted 3× because discussion depth predicts LinkedIn content value better than raw popularity.

### Content type classifier

Every post is auto-labeled before the digest is generated:

| Label | What it means |
|-------|--------------|
| `ANNOUNCEMENT` | New release, launch, or update |
| `CVE` | Security vulnerability or exploit |
| `DISCUSSION` | Question or debate thread |
| `TUTORIAL` | Guide or how-to |
| `INSIGHT` | Research, data, or study |
| `MEME` | Only passes if score ≥ 1,000 (cultural moment) |

### LinkedIn angle map

Each `(category, content_type)` pair maps to a pre-written angle tag. No Claude tokens spent on figuring out what to write — only on writing it.

---

## Categories

| Folder | Subreddits |
|--------|-----------|
| `ai_claude` | r/ClaudeAI, r/artificial, r/MachineLearning, r/LocalLLaMA, r/singularity, r/OpenAI, r/ChatGPT |
| `personal_branding` | r/personalbranding, r/Entrepreneur, r/marketing, r/LinkedInTips, r/content_marketing, r/GrowthHacking |
| `vc_funding` | r/venturecapital, r/startups, r/ycombinator, r/IndiaStartups, r/smallbusiness |
| `cybersecurity` | r/netsec, r/cybersecurity, r/AskNetsec, r/hacking, r/blueteamsec, r/malware |

---

## Output structure

```
data/
├── ai_claude/
│   ├── latest_daily.json       ← always the most recent daily (full scored data)
│   ├── latest_weekly.json      ← always the most recent weekly
│   ├── daily/2026-04-20.json
│   └── weekly/2026-04-20.json
├── personal_branding/
├── vc_funding/
└── cybersecurity/

digests/
├── daily/2026-04-20.md         ← ~500 token compressed digest (becomes GitHub Issue)
└── weekly/2026-04-20.md        ← ~1,200 token weekly research digest
```

---

## Setup (fork this repo)

### 1. Enable GitHub Issues

Your repo → Settings → Features → check **Issues**.

### 2. That's it.

No secrets needed. `GITHUB_TOKEN` is automatic. The pipeline uses Reddit's free public JSON API — no OAuth, no API keys, no Composio.

GitHub Actions will now:
- Create labeled Issues automatically (`daily-digest`, `weekly-research`)
- You get notified via GitHub's own push notification / email
- Issues are permanently searchable by label, date, keyword

---

## Schedules

| Workflow | Schedule | Output |
|----------|----------|--------|
| Daily scrape | Every day at 05:30 IST | Top posts of the day, scored + filtered |
| Weekly research | Sunday at 06:30 IST | Top posts of the week + comments + search intelligence |

Both workflows also have a **manual trigger** (Actions tab → Run workflow).

---

## Local run

```bash
pip install httpx

python scrapers/daily_scraper.py
python scrapers/weekly_scraper.py
```

---

## Using the digest with Claude

The daily Issue is ~500 tokens. Paste it and say:

> *"Write me 3 LinkedIn posts from this digest."*

Total Claude session: ~1,700 tokens vs ~25,000 tokens for raw Reddit data — **94% reduction** with better signal.

---

## File structure

```
reddit-intelligence/
├── config/
│   ├── subreddits.json          # subreddit lists + per-category limits
│   └── research_plan.json       # weekly search queries + score thresholds
├── scrapers/
│   ├── reddit_client.py         # Composio SDK wrapper (3 functions)
│   ├── daily_scraper.py         # daily flow: fetch → score → digest → save
│   └── weekly_scraper.py        # weekly flow: top posts + comments + search
├── processors/
│   ├── scorer.py                # engagement formula + content type + angle map
│   ├── digest.py                # generates the compressed markdown digest
│   └── cleaner.py               # strips junk fields, caps selftext
├── .github/workflows/
│   ├── daily_scrape.yml
│   └── weekly_research.yml
├── data/                        # full scored JSON archive
└── digests/                     # compressed markdown digests
```

---

Built by [@prathamratna](https://github.com/prathamratna)
