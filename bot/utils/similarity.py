from __future__ import annotations
import re
import unicodedata
from typing import Optional

_ws_re = re.compile(r"\s+", re.U)

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = s.lower()
    s = _ws_re.sub(" ", s)
    return s.strip()

def _words(s: str) -> list[str]:
    return [w for w in re.split(r"[^\w]+", _norm(s), flags=re.U) if w]

def contains_phrase(seed: str, text: str) -> bool:
    """
    Строго по порядку, без 'лишних' слов между токенами (но допускает пунктуацию/переносы).
    """
    words = _words(seed)
    if not words:
        return False
    parts = [r"\b" + re.escape(words[0]) + r"\b"]
    for w in words[1:]:
        parts.append(r"\W+")
        parts.append(r"\b" + re.escape(w) + r"\b")
    pattern = "".join(parts)
    return re.search(pattern, _norm(text), flags=re.IGNORECASE | re.UNICODE) is not None

def contains_phrase_with_gap(seed: str, text: str, max_gap_words: int = 3) -> bool:
    """
    Строго по порядку ЗНАЧИМЫХ слов, допускаем до N посторонних слов между ними.
    Пример: 'они-то собираются против нас восстать в будущем'
    найдётся и в тексте 'они-то уже явно собираются против нас скоро восстать в будущем'.
    """
    words = _words(seed)
    if not words:
        return False
    # между целевыми токенами разрешаем: (не-слово+слово){0,max_gap} + не-слово+
    gap = rf"(?:\W+\w+){{0,{max_gap_words}}}\W+"
    parts = [rf"\b{re.escape(words[0])}\b"]
    for w in words[1:]:
        parts.append(gap)
        parts.append(rf"\b{re.escape(w)}\b")
    pattern = "".join(parts)
    return re.search(pattern, _norm(text), flags=re.IGNORECASE | re.UNICODE) is not None

def match_score(seed: str, text: str) -> float:
    sw = _words(seed); tw = _words(text)
    if not sw or not tw:
        return 0.0
    hits = sum(1 for w in sw if re.search(rf"\b{re.escape(w)}\b", " ".join(tw)))
    return hits / len(sw)

def find_match_window(seed: str, text: str, pad: int = 90) -> Optional[str]:
    t = unicodedata.normalize("NFC", text or "")
    words = _words(seed)
    if not words:
        return None
    gap = rf"(?:\W+\w+){{0,3}}\W+"
    parts = [rf"\b{re.escape(words[0])}\b"]
    for w in words[1:]:
        parts.append(gap); parts.append(rf"\b{re.escape(w)}\b")
    pattern = "".join(parts)
    m = re.search(pattern, t, flags=re.IGNORECASE | re.UNICODE)
    if not m:
        return None
    i = max(0, m.start() - pad)
    j = min(len(t), m.end() + pad)
    snippet = t[i:j].strip()
    if i > 0: snippet = "…" + snippet
    if j < len(t): snippet = snippet + "…"
    return snippet
