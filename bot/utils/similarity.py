import re
import unicodedata

WORD_RE = re.compile(r"[\w\-]+", flags=re.U)

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    # replace long dash variants with normal hyphen/space
    s = s.replace("—", "-").replace("–", "-").replace("‑", "-")
    return s

def tokenize(s: str) -> list[str]:
    return [w for w in WORD_RE.findall(normalize_text(s)) if w]

def seed_match_ratio(seed: str, text: str) -> float:
    seed_tokens = tokenize(seed)
    if not seed_tokens:
        return 0.0
    text_tokens = set(tokenize(text))
    hits = sum(1 for t in seed_tokens if t in text_tokens)
    return hits / max(len(seed_tokens), 1)
