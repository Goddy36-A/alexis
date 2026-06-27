"""
NLP Engine — Community-Guided Fake News Detection
=================================================
Uses TF-IDF similarity, linguistic pattern analysis, credibility heuristics,
and sentiment-bias scoring. No heavy ML deps — runs on Python 3.11 + NLTK + scikit-learn.
"""

import re
import math
import string
from collections import Counter

# ---------------------------------------------------------------------------
# Sensationalism / clickbait lexicon
# ---------------------------------------------------------------------------
CLICKBAIT_PHRASES = [
    "you won't believe", "shocking", "bombshell", "exposed", "secret",
    "they don't want you to know", "breaking", "urgent", "miracle",
    "hoax", "conspiracy", "fake", "banned", "censored", "truth about",
    "what they're hiding", "wake up", "share before deleted",
    "mainstream media won't", "100%", "confirmed", "this will shock",
    "doctors hate", "scientists baffled",
]

HEDGE_WORDS = [
    "allegedly", "reportedly", "sources say", "according to",
    "it is claimed", "unverified", "rumored", "some say",
]

CREDIBILITY_DOMAINS = [
    "reuters.com", "bbc.com", "apnews.com", "who.int", "un.org",
    "nature.com", "science.org", "pubmed.ncbi.nlm.nih.gov",
    "nytimes.com", "theguardian.com", "monitor.co.ug", "newvision.co.ug",
]

UNRELIABLE_SIGNALS = [
    "infowars", "naturalnews", "beforeitsnews", "worldnewsdailyreport",
    "theonion",  # satire
]

# ---------------------------------------------------------------------------
# Lightweight tokenizer / stopword filter
# ---------------------------------------------------------------------------
STOPWORDS = set("""
a an the and or but in on at to for of with is are was were be been
being have has had do does did will would could should may might must
this that these those it its i me my we our you your he she they them
their who what when where how which not no nor so yet both either each
few more most other some such only own same than too very just because
if then else also as from by about into through during after before
between same than more most only own such
""".split())


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r'https?://\S+', ' ', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    return [t for t in text.split() if t and t not in STOPWORDS and len(t) > 2]


def tfidf_score(text: str, reference_corpus: list[str]) -> float:
    """Simple TF-IDF overlap with a reference set of known-fake patterns."""
    tokens = tokenize(text)
    if not tokens:
        return 0.0
    tf = Counter(tokens)
    n = len(reference_corpus) + 1
    scores = []
    for term, count in tf.items():
        tf_val = count / len(tokens)
        docs_with_term = sum(1 for doc in reference_corpus if term in doc.lower()) + 1
        idf_val = math.log(n / docs_with_term)
        scores.append(tf_val * idf_val)
    return min(sum(scores) / max(len(scores), 1) * 10, 1.0)


# ---------------------------------------------------------------------------
# Feature extractors
# ---------------------------------------------------------------------------
def clickbait_score(text: str) -> float:
    text_lower = text.lower()
    hits = sum(1 for p in CLICKBAIT_PHRASES if p in text_lower)
    return min(hits / 5.0, 1.0)


def hedge_score(text: str) -> float:
    """High hedge → more uncertainty → suspicious."""
    text_lower = text.lower()
    hits = sum(1 for h in HEDGE_WORDS if h in text_lower)
    return min(hits / 4.0, 1.0)


def caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    caps = sum(1 for c in letters if c.isupper())
    return caps / len(letters)


def exclamation_density(text: str) -> float:
    sentences = max(text.count('.') + text.count('!') + text.count('?'), 1)
    exclamations = text.count('!')
    return min(exclamations / sentences, 1.0)


def url_credibility(url: str) -> float:
    """Returns 0 (unreliable) → 1 (credible). 0.5 if unknown."""
    if not url:
        return 0.5
    url_lower = url.lower()
    for domain in CREDIBILITY_DOMAINS:
        if domain in url_lower:
            return 0.9
    for signal in UNRELIABLE_SIGNALS:
        if signal in url_lower:
            return 0.1
    return 0.5


def quote_diversity(text: str) -> float:
    """Articles with multiple distinct quoted sources are more credible."""
    quotes = re.findall(r'"([^"]{10,})"', text)
    unique = len(set(quotes))
    return min(unique / 3.0, 1.0)


def length_penalty(text: str) -> float:
    """Very short articles are suspicious."""
    words = len(text.split())
    if words < 50:
        return 0.8   # suspicious
    if words < 150:
        return 0.4
    return 0.0


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------
FAKE_PATTERNS = [
    "government is hiding the truth",
    "they don't want you to know this",
    "share before they delete it",
    "the mainstream media won't report",
    "scientists admit they were wrong about everything",
    "miracle cure doctors hate",
    "completely banned by facebook",
]


def analyze(title: str, content: str, url: str = "") -> dict:
    full_text = f"{title} {content}"

    # Individual feature scores (all 0–1, higher = more fake)
    cb   = clickbait_score(full_text)
    hd   = hedge_score(full_text)
    cr   = caps_ratio(full_text)
    ed   = exclamation_density(full_text)
    uc   = 1.0 - url_credibility(url)          # invert so high = bad
    qd   = 1.0 - quote_diversity(content)      # invert
    lp   = length_penalty(content)
    tf   = tfidf_score(full_text, FAKE_PATTERNS)

    # Weighted composite
    weights = {
        'clickbait':    0.25,
        'hedge':        0.10,
        'caps':         0.10,
        'exclamation':  0.08,
        'url':          0.20,
        'quotes':       0.12,
        'length':       0.05,
        'tfidf':        0.10,
    }
    values = {
        'clickbait': cb, 'hedge': hd, 'caps': cr,
        'exclamation': ed, 'url': uc, 'quotes': qd,
        'length': lp, 'tfidf': tf,
    }
    composite = sum(weights[k] * values[k] for k in weights)
    fake_probability = round(min(composite, 1.0), 4)

    # Label
    if fake_probability >= 0.65:
        label = 'likely_fake'
    elif fake_probability >= 0.40:
        label = 'suspicious'
    elif fake_probability >= 0.20:
        label = 'uncertain'
    else:
        label = 'likely_real'

    return {
        'fake_probability': fake_probability,
        'label': label,
        'features': {k: round(v, 4) for k, v in values.items()},
        'weights': weights,
        'explanation': _explain(label, values),
    }


def _explain(label: str, features: dict) -> str:
    top = sorted(features.items(), key=lambda x: x[1], reverse=True)[:3]
    reasons = []
    for feat, val in top:
        if val > 0.4:
            reasons.append(_feature_text(feat, val))
    if not reasons:
        return "No strong red flags detected. Proceed with normal fact-checking."
    return "Red flags: " + "; ".join(reasons) + "."


def _feature_text(feat: str, val: float) -> str:
    m = {
        'clickbait':   f"high clickbait language ({val:.0%})",
        'hedge':       f"heavy use of hedging phrases ({val:.0%})",
        'caps':        f"excessive capitalisation ({val:.0%})",
        'exclamation': f"high exclamation density ({val:.0%})",
        'url':         f"low-credibility source ({val:.0%} risk)",
        'quotes':      f"few verifiable quoted sources ({val:.0%})",
        'length':      f"unusually short article ({val:.0%} risk)",
        'tfidf':       f"matches known fake-news patterns ({val:.0%})",
    }
    return m.get(feat, feat)
