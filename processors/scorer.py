"""
Scorer — all intelligence logic runs here in pure Python, zero Claude tokens.

Three jobs:
  1. Quality gate: reject posts below per-subreddit score thresholds
  2. Content type: classify posts by regex into actionable categories
  3. LinkedIn angle: map (category, content_type) -> pre-written angle tag

The engagement score formula weights comments 3x over upvotes because
discussion depth predicts LinkedIn content value better than raw popularity.
"""

import re

# ---------------------------------------------------------------------------
# Per-subreddit minimum score gates
# Small subs (5k members) and large subs (700k members) need different bars.
# ---------------------------------------------------------------------------
MIN_SCORES: dict[str, int] = {
    # AI & Claude
    "ClaudeAI": 200,
    "artificial": 100,
    "MachineLearning": 150,
    "LocalLLaMA": 100,
    "singularity": 100,
    "OpenAI": 100,
    "ChatGPT": 100,
    # Personal Branding
    "personalbranding": 5,
    "Entrepreneur": 50,
    "marketing": 30,
    "LinkedInTips": 10,
    "content_marketing": 10,
    "GrowthHacking": 20,
    # VC & Funding
    "venturecapital": 15,
    "startups": 50,
    "ycombinator": 30,
    "IndiaStartups": 5,
    "smallbusiness": 20,
    # Cybersecurity
    "netsec": 30,
    "cybersecurity": 50,
    "AskNetsec": 15,
    "hacking": 30,
    "blueteamsec": 20,
    "malware": 20,
}
DEFAULT_MIN_SCORE = 10

# ---------------------------------------------------------------------------
# Content type patterns — order matters, first match wins
# ---------------------------------------------------------------------------
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("CVE",          re.compile(r'\bCVE-\d{4}-\d+\b|vulnerabilit|exploit|0-day|RCE|bypass|patch\b|breach\b', re.I)),
    ("ANNOUNCEMENT", re.compile(r'\b(introduc|announc|releas|launch|new feature|updat|v\d+\.\d+)\w*\b', re.I)),
    ("TUTORIAL",     re.compile(r'\bhow[- ]to\b|\bguide\b|\btips?\b|\blearn\b|\btutorial\b|\bstep[- ]by[- ]step\b', re.I)),
    ("INSIGHT",      re.compile(r'\bresearch\b|\bstudy\b|\bdata\b|\breport\b|\banalysis\b|\btrend\b|\bpredict\b|\bfound that\b', re.I)),
    ("DISCUSSION",   re.compile(r'\?$|^\s*(why|how|should|is it|what do|thoughts|opinion|anyone|debate|unpopular)', re.I)),
    ("MEME",         re.compile(r'\bme when\b|\bpov:\b|\blmao\b|\blol\b|💀|😭|😂|\bngl\b|\bbruh\b|\bbased\b', re.I)),
]

# ---------------------------------------------------------------------------
# LinkedIn angle map — pre-written, no Claude tokens needed
# ---------------------------------------------------------------------------
_ANGLES: dict[tuple[str, str], str] = {
    ("ai_claude", "ANNOUNCEMENT"):   "First-mover take — react within 6 hrs, high engagement window",
    ("ai_claude", "DISCUSSION"):     "Contrarian or supporting POV — react content performs well here",
    ("ai_claude", "MEME"):           "Cultural moment — use as hook/opener, don't copy the meme",
    ("ai_claude", "TUTORIAL"):       "Simplified explainer — builds credibility with non-technical audience",
    ("ai_claude", "INSIGHT"):        "Data-backed take — cite the finding, add your lived angle",
    ("ai_claude", "CVE"):            "AI safety/security signal — rare angle in AI discourse",
    ("personal_branding", "DISCUSSION"): "Answer the question + share your founder experience directly",
    ("personal_branding", "INSIGHT"):    "Research-backed branding tip — formats well as a list post",
    ("personal_branding", "TUTORIAL"):   "Practical framework — step-by-step list format performs well",
    ("personal_branding", "ANNOUNCEMENT"): "New platform/tool reaction — first-take opportunity",
    ("vc_funding", "DISCUSSION"):   "Founder/builder POV — what VCs miss from the trenches",
    ("vc_funding", "ANNOUNCEMENT"): "Market signal — what this funding round means for founders",
    ("vc_funding", "INSIGHT"):      "Funding landscape take — data + your perspective as a builder",
    ("cybersecurity", "CVE"):       "Security awareness — break it down for non-technical founders",
    ("cybersecurity", "TUTORIAL"):  "Practical security tip for startup teams — educational post",
    ("cybersecurity", "DISCUSSION"):"Security lesson for builders — make it relevant to startups",
    ("cybersecurity", "INSIGHT"):   "Threat landscape signal — positions you as security-aware founder",
}
_DEFAULT_ANGLE = "Thought leadership opportunity — add your unique founder perspective"

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def engagement_score(post: dict) -> float:
    """
    Comments are weighted 3x over upvotes.
    A post with 50 upvotes and 200 comments > 500 upvotes and 5 comments.
    Discussion depth predicts LinkedIn content value better than raw popularity.
    """
    return (post.get("score", 0) * 1.0) + (post.get("num_comments", 0) * 3.0)


def content_type(post: dict) -> str:
    """Classify a post by its title using ordered regex patterns."""
    title = post.get("title", "")
    for type_name, pattern in _PATTERNS:
        if pattern.search(title):
            return type_name
    return "GENERAL"


def passes_gate(post: dict) -> bool:
    """Return True if the post meets its subreddit's minimum score threshold."""
    subreddit_name = post.get("subreddit", "r/unknown").replace("r/", "")
    min_score = MIN_SCORES.get(subreddit_name, DEFAULT_MIN_SCORE)
    return post.get("score", 0) >= min_score


def linkedin_angle(category: str, post_type: str) -> str:
    return _ANGLES.get((category, post_type), _DEFAULT_ANGLE)


def score_post(post: dict, category: str) -> dict | None:
    """
    Enrich a post with intelligence fields.
    Returns None if the post fails the quality gate or is a dead meme.
    """
    if not passes_gate(post):
        return None

    p_type = content_type(post)

    # Memes only pass if viral (score >= 1000) — cultural moments worth noting
    if p_type == "MEME" and post.get("score", 0) < 1000:
        return None

    return {
        **post,
        "content_type":     p_type,
        "engagement_score": round(engagement_score(post), 1),
        "linkedin_angle":   linkedin_angle(category, p_type),
    }
