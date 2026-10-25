"""Порядок результатов поиска. Общий для сервера и клиента.

Две одинаковые копии: search_rank.py (клиент) и server/search_rank.py (сервер на Pi
ставится отдельно от клиента, общего импорта у них нет). Менять обе сразу.

Чем меньше ранг, тем выше строка:
    0  исполнитель — ровно запрос                «limp bizkit» -> Limp Bizkit
    1  запрос — целое слово в исполнителе        «limp»        -> Limp Bizkit, Limp Bizkit Feat. ...
    2  запрос — целое слово в названии           «eyes»        -> Behind Blue Eyes
    3  исполнитель начинается с запроса          «lim»         -> Limp Bizkit
    4  подстрока в исполнителе
    5  название начинается с запроса
    6  подстрока в названии
    7  всё остальное (альбом, имя файла, папки)
Внутри одного ранга порядок задаёт вызывающий: исполнитель, альбом, путь.
"""
import re


def fold(s) -> str:
    """Регистр и ё не важны. None -> ''."""
    return (s or "").casefold().replace("ё", "е")


def _is_word(q: str, text: str) -> bool:
    """q стоит в text отдельным словом (или фразой), а не куском другого слова."""
    return re.search(r"(?<!\w)" + re.escape(q) + r"(?!\w)", text) is not None


def rank(query: str, title: str, author: str = "") -> int:
    """Ранг одного результата. query, title, author — как есть, приводятся здесь."""
    q = fold(query).strip()
    if not q:
        return 7
    a, t = fold(author), fold(title)
    if a and a == q:
        return 0
    if a and _is_word(q, a):
        return 1
    if _is_word(q, t):
        return 2
    if a.startswith(q):
        return 3
    if q in a:
        return 4
    if t.startswith(q):
        return 5
    if q in t:
        return 6
    return 7
