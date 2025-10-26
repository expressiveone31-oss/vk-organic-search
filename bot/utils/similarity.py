
from __future__ import annotations
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Tuple

WORD_RE = re.compile(r"[\w\-]+", flags=re.U)

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = (s.replace("—", "-").replace("–", "-").replace("‑", "-")
           .replace("ё", "е").replace("’", "'").replace("“",""").replace("”","""))
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def tokenize(s: str) -> list[str]:
    return [w for w in WORD_RE.findall(normalize_text(s)) if w]

def contains_phrase(seed: str, text: str) -> bool:
    ns = normalize_text(seed)
    nt = normalize_text(text)
    return bool(ns) and ns in nt

def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def match_score(seed: str, text: str) -> float:
    """Heuristic 0..1 score for fuzzy match.
    Priority:
      1) exact phrase -> 1.0
      2) token Jaccard overlap
      3) SequenceMatcher ratio on normalized strings
    """
    if contains_phrase(seed, text):
        return 1.0
    stoks = set(tokenize(seed))
    ttoks = set(tokenize(text))
    jac = jaccard(stoks, ttoks)
    if jac >= 0.75 and len(stoks) >= 2:
        return 0.9
    # final fallback on overall string similarity
    ns = normalize_text(seed)
    nt = normalize_text(text)
    if not ns or not nt:
        return 0.0
    ratio = SequenceMatcher(None, ns, nt).ratio()
    # dampen very short texts
    if len(nt) < 40:
        ratio *= 0.85
    return max(jac, ratio * 0.8)

def find_match_window(seed: str, text: str, pad: int = 60) -> str:
    """Return a short preview around the best match."""
    raw = text or ""
    if contains_phrase(seed, raw):
        nt = normalize_text(raw)
        ns = normalize_text(seed)
        i = nt.find(ns)
        # map indices back approximately by using the original raw string length proportion
        # simple safe fallback:
        left = max(0, max(i - pad, 0))
        right = min(len(nt), i + len(ns) + pad)
        snippet = nt[left:right]
        prefix = "…" if left > 0 else ""
        suffix = "…" if right < len(nt) else ""
        return f"{prefix}{snippet}{suffix}"
    # fallback: first 120 chars
    return (raw[:120] + ("…" if len(raw) > 120 else ""))
