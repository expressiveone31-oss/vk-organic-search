from __future__ import annotations
import re, unicodedata
from difflib import SequenceMatcher

WORD_RE = re.compile(r"[\w\-]+", flags=re.U)

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = (s.replace("—","-").replace("–","-").replace("‑","-").replace("ё","е")
         .replace("’","'").replace("“",'"').replace("”",'"'))
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def tokenize(s: str) -> list[str]:
    return [w for w in WORD_RE.findall(normalize_text(s)) if w]

def contains_phrase(seed: str, text: str) -> bool:
    ns = normalize_text(seed); nt = normalize_text(text)
    return bool(ns) and ns in nt

def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b: return 0.0
    inter = len(a & b); union = len(a | b)
    return inter/union if union else 0.0

def match_score(seed: str, text: str) -> float:
    if contains_phrase(seed, text): return 1.0
    stoks, ttoks = set(tokenize(seed)), set(tokenize(text))
    jac = jaccard(stoks, ttoks)
    if jac >= 0.75 and len(stoks) >= 2: return 0.9
    ns, nt = normalize_text(seed), normalize_text(text)
    if not ns or not nt: return 0.0
    ratio = SequenceMatcher(None, ns, nt).ratio()
    if len(nt) < 40: ratio *= 0.85
    return max(jac, ratio * 0.8)

def find_match_window(seed: str, text: str, pad: int = 60) -> str:
    raw = text or ""
    ns, nt = normalize_text(seed), normalize_text(raw)
    i = nt.find(ns)
    if i >= 0:
        left, right = max(0, i-pad), min(len(nt), i+len(ns)+pad)
        prefix = "…" if left>0 else ""; suffix = "…" if right<len(nt) else ""
        return f"{prefix}{nt[left:right]}{suffix}"
    return (raw[:120] + ("…" if len(raw) > 120 else ""))
