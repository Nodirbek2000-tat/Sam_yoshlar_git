"""Mahalla (MFY) nomi: odamlar o'zi yozadi, ro'yxat yo'q.

Bir mahallani har kim har xil yozadi: «Bog'ishamol MFY», «bogishamol mfy»,
«Bog‘ishamol mahallasi». Saqlashda faqat ortiqcha bo'shliq tozalanadi,
statistikada esa `mahalla_key` bo'yicha bitta qatorga yig'iladi.
"""

import re

MIN_LENGTH = 3
MAX_LENGTH = 150

_APOSTROPHES = re.compile(r"[‘’ʻʼ`´']")
_SUFFIXES = re.compile(
    r"\b(m\s*\.?\s*f\s*\.?\s*y\s*\.?|mahallasi|mahalla|fuqarolar\s+yig['‘’ʻ]?ini|qishlog['‘’ʻ]?i)\b",
    re.IGNORECASE)


def clean_mahalla(raw):
    """Saqlanadigan ko'rinish: bo'shliqlar tozalangan. Juda qisqa/uzun bo'lsa — None."""
    value = re.sub(r'\s+', ' ', str(raw or '')).strip()
    if not MIN_LENGTH <= len(value) <= MAX_LENGTH:
        return None
    return value


def mahalla_key(raw):
    """Guruhlash kaliti: kichik harf, tutuq belgisiz, «MFY»/«mahallasi» so'zlarisiz."""
    value = _APOSTROPHES.sub('', str(raw or '').lower())
    value = _SUFFIXES.sub(' ', value)
    value = re.sub(r'[^\w\s-]', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()
