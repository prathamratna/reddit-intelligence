# reddit-intelligence

Automated Reddit data pipeline for LinkedIn research. Runs free on GitHub Actions.

No OAuth. No API keys. Just Reddit's public `.json` API.

## What it does

- **Daily** (05:30 IST): Top posts of the day from each category → clean JSON
- **Weekly** (06:30 IST Sunday): Top posts of the week + comments + patterns → clean JSON

## Categories

| Folder | Subreddits |
|---|---|
| `ai_claude` | r/ClaudeAI, r/artificial, r/MachineLearning, r/LocalLLaMA, r/singularity, r/OpenAI |
| `personal_branding` | r/personalbranding, r/Entrepreneur, r/marketing, r/LinkedInTips |
| `vc_funding` | r/venturecapital, r/startups, r/ycombinator, r/IndiaStartups |
| `cybersecurity` | r/netsec, r/cybersecurity, r/AskNetsec, r/hacking |

## Data structure

```
data/
├── ai_claude/
│   ├── latest_daily.json     ← always the most recent daily
│   ├── latest_weekly.json    ← always the most recent weekly
│   ├── daily/2026-04-19.json
│   └── weekly/2026-04-19.json
├── personal_branding/
├── vc_funding/
└── cybersecurity/
```

Every post includes a direct `url` field → click to open the original Reddit thread.

## Setup

1. Fork this repo
2. GitHub Actions runs automatically — no configuration needed
3. Manual trigger: Actions tab → select workflow → Run workflow

## Local run

```bash
pip install httpx
python scrapers/daily_scraper.py
python scrapers/weekly_scraper.py
```

## How to use with Claude

Paste the contents of any `latest_daily.json` or `latest_weekly.json` directly into Claude.
Each post has a `url` field you can click to verify the source.
