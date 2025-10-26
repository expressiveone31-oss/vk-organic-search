from __future__ import annotations
import re
import unicodedata
from typing import Optional

_ws_re = re.compile(r"\s+", re.U)

def _norm(s: str) -> str:
    # Unicode NFC, нижний регистр, схлопываем пробелы
    s = unicodedata.normalize("NFC", s or "")
    s = s.lower()
    s = _ws_re.sub(" ", s)
    return s.strip()

def contains_phrase(seed: str, text: str) -> bool:
    """
    'Строгий' матч: сохраняем порядок слов seed,
    но допускаем любые разделители между ними в тексте:
    пробелы/переносы/знаки препинания/эмодзи и т.д.
    Пример: "и вот они-то собираются ... восстать в будущем?"
    """
    s = _norm(seed)
    t = _norm(text)

    # слова из seed (игнорируем «служебные» разделители внутри)
    words = [w for w in re.split(r"[^\w]+", s, flags=re.U) if w]
    if not words:
        return False

    # строим regex вида: \bслово1\b\W+слово2\W+...\bсловоN\b
    # \W+ охватывает любые небуквенно-цифровые разделители (включая эмодзи)
    parts = [r"\b" + re.escape(words[0]) + r"\b"]
    for w in words[1:]:
        parts.append(r"\W+")
        parts.append(r"\b" + re.escape(w) + r"\b")
    pattern = "".join(parts)

    return re.search(pattern, t, flags=re.IGNORECASE | re.UNICODE) is not None

def match_score(seed: str, text: str) -> float:
    """
    Простой «fuzzy» счётчик: доля совпавших слов seed в тексте.
    Используется для VK, где нужен более свободный поиск.
    """
    s = _norm(seed)
    t = _norm(text)
    if not s or not t:
        return 0.0
    sw = [w for w in re.split(r"[^\w]+", s) if w]
    if not sw:
        return 0.0
    hits = sum(1 for w in sw if re.search(r"\b" + re.escape(w) + r"\b", t))
    return hits / len(sw)

def find_match_window(seed: str, text: str, pad: int = 80) -> Optional[str]:
    """
    Ищем окно вокруг первого совпадения (для сниппета).
    """
    t = unicodedata.normalize("NFC", text or "")
    s = unicodedata.normalize("NFC", seed or "")
    # используем тот же «строгий, но гибкий» паттерн
    words = [w for w in re.split(r"[^\w]+", s.lower()) if w]
    if not words:
        return None
    parts = [r"\b" + re.escape(words[0]) + r"\b"]
    for w in words[1:]:
        parts.append(r"\W+")
        parts.append(r"\b" + re.escape(w) + r"\b")
    pattern = "".join(parts)
    m = re.search(pattern, t, flags=re.IGNORECASE | re.UNICODE)
    if not m:
        return None
    i = max(0, m.start() - pad)
    j = min(len(t), m.end() + pad)
    snippet = t[i:j].strip()
    if i > 0:
        snippet = "…" + snippet
    if j < len(t):
        snippet = snippet + "…"
    return snippet
