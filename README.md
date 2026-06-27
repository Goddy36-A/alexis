# CFND — Community-Guided Fake News Detection System
**Final Year Project | Ideawood Uganda | Python 3.11 · Flask · SQLite3 · NLP**

---

## Overview

CFND is a community-powered fake news detection web application that combines:

- **NLP Analysis** — Automated first-pass scoring using TF-IDF pattern matching, clickbait detection, linguistic hedging analysis, source credibility heuristics, and sentiment-bias scoring.
- **Community Voting** — Weighted confidence votes where each member rates an article as *Fake*, *Real*, or *Unsure* with a confidence level (1–5). Verdicts update dynamically.
- **Expert Review** — Verified fact-checkers can override community verdicts with sourced explanations.
- **Reputation & Gamification** — Badges and a leaderboard reward consistent, accurate fact-checking participation.
- **REST API** — JSON endpoints for external integration and mobile clients.

---

## Architecture

```
cfnd/
├── run.py                  # Entry point
├── seed.py                 # Demo data seeder
├── requirements.txt
├── cfnd.db                 # SQLite database (auto-created)
└── app/
    ├── __init__.py         # Flask app factory
    ├── database.py         # SQLite connection & schema
    ├── nlp_engine.py       # NLP scoring pipeline
    ├── routes.py           # Main blueprint (feed, submit, vote, comment)
    ├── auth.py             # Auth blueprint (register, login, logout)
    ├── api.py              # REST API blueprint (/api/*)
    └── templates/
        ├── base.html
        ├── index.html
        ├── article.html
        ├── submit.html
        ├── leaderboard.html
        ├── dashboard.html
        └── auth/
            ├── login.html
            └── register.html
```

---

## Database Schema

| Table           | Purpose                                        |
|-----------------|------------------------------------------------|
| `users`         | Accounts with role (user / expert / admin)     |
| `articles`      | Submitted articles with NLP scores             |
| `votes`         | Community votes with confidence weights        |
| `comments`      | Discussion threads per article                 |
| `expert_reviews`| Verified fact-checker overrides                |
| `badges`        | Gamification rewards                           |

---

## NLP Engine Features

The `nlp_engine.py` module requires **zero heavy ML dependencies** — it runs on pure Python 3.11 with no CUDA or large model files:

| Feature            | Weight | Description                                         |
|--------------------|--------|-----------------------------------------------------|
| Clickbait score    | 25%    | Detects sensationalist phrases                      |
| URL credibility    | 20%    | Known reliable vs unreliable domain list            |
| Hedge words        | 10%    | Excessive "reportedly / allegedly" signals doubt    |
| Caps ratio         | 10%    | Excessive CAPITALISATION                            |
| Quote diversity    | 12%    | Few verifiable quotes = low credibility             |
| TF-IDF patterns    | 10%    | Similarity to known fake-news sentence patterns     |
| Exclamation density| 8%     | Emotional punctuation overuse                       |
| Length penalty     | 5%     | Very short articles are suspicious                  |

**Labels**: `likely_real` · `uncertain` · `suspicious` · `likely_fake`

---

## Verdict Logic

```
Community verdict (requires ≥ 3 votes):
  weighted_fake_ratio ≥ 0.60  →  FAKE
  weighted_fake_ratio ≤ 0.35  →  REAL
  otherwise                   →  PENDING

Expert review overrides community verdict unconditionally.
```

---

## Setup & Run

### Requirements
- Python 3.11.8
- pip

### Install

```bash
git clone <repo>
cd cfnd
pip install -r requirements.txt
```

### Run

```bash
python run.py
```

Open http://localhost:5000

### Seed with demo data

```bash
python seed.py
```

Demo accounts:

| Username  | Password   | Role   |
|-----------|------------|--------|
| admin     | admin123   | admin  |
| expert1   | expert123  | expert |
| alice     | alice123   | user   |
| bob       | bob123     | user   |

---

## REST API

| Endpoint                        | Method | Description                    |
|---------------------------------|--------|--------------------------------|
| `/api/analyze`                  | POST   | Run NLP on any article         |
| `/api/articles`                 | GET    | Paginated article list         |
| `/api/article/<id>/stats`       | GET    | Detailed verdict stats         |
| `/api/leaderboard`              | GET    | Top 10 community members       |

### Example: Analyze via API

```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"title":"SHOCKING: Miracle cure doctors HATE", "content":"You wont believe...", "url":""}'
```

Response:
```json
{
  "fake_probability": 0.72,
  "label": "likely_fake",
  "features": { "clickbait": 0.8, "url": 0.5, ... },
  "explanation": "Red flags: high clickbait language (80%); few verifiable sources (75%)."
}
```

---

## FYP Research Context

### Problem
Disinformation spreads faster than corrections in low-resource language communities. Automated fact-checking systems trained on English data perform poorly on Ugandan news contexts.

### Solution
A hybrid system that combines:
1. **Automated NLP pre-screening** (fast, language-agnostic heuristics)
2. **Community wisdom aggregation** (local context, confidence weighting)
3. **Expert override mechanism** (ground truth anchoring)

### Contributions
- Confidence-weighted voting model that reduces influence of low-certainty votes
- NLP pipeline that works without GPU or large pretrained models — deployable in low-resource environments (Termux/Android)
- Gamification layer to incentivise consistent, high-quality community participation

### Future Work
- Fine-tune a multilingual classifier on Runyankole-Rukiga and Luganda news corpora
- Integrate with Omuhingi translator for cross-lingual article analysis
- Mobile-first Progressive Web App wrapper
- Federated trust network across university campuses

---

## License
MIT — Ideawood Uganda / Kitara Kid, 2025
