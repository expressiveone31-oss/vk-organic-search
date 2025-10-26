# вверху файла:
from bot.utils.similarity import contains_phrase, contains_phrase_with_gap, match_score, find_match_window
GAP_WORDS = int(os.getenv("TELEMETR_MAX_GAP_WORDS", "3"))

# ... внутри _search_telemetr(...)
    for it in items:
        ch = it.get("channel") or {}
        body = _telemetr_body(it)
        if not body:
            continue

        ok = False
        if TELEMETR_STRICT:
            # сначала совсем строго, потом — с допуском до GAP_WORDS слов между токенами
            ok = contains_phrase(seed, body) or contains_phrase_with_gap(seed, body, max_gap_words=GAP_WORDS)
        else:
            ok = match_score(seed, body) >= TELEMETR_FUZZY_THRESHOLD
        if not ok:
            continue
        # ... дальше без изменений (формирование Publication)
