from __future__ import annotations

import re
from typing import Any

INDIAN_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "ta": "Tamil",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
}

INDIAN_LANGUAGE_CODES = tuple(INDIAN_LANGUAGES)

_INDIC_RANGES = [
    ("ta", "\u0B80-\u0BFF"),
    ("kn", "\u0C80-\u0CFF"),
    ("ml", "\u0D00-\u0D7F"),
    ("te", "\u0C00-\u0C4F"),
    ("bn", "\u0980-\u09FF"),
    ("or", "\u0B00-\u0B7F"),
    ("gu", "\u0A80-\u0AFF"),
    ("pa", "\u0A00-\u0A7F"),
    ("hi", "\u0900-\u097F"),
]

_STOPWORDS = {
    "the", "and", "or", "is", "are", "a", "an", "in", "on", "at", "to", "of",
    "for", "with", "by", "from", "it", "its", "this", "that", "these", "those",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "i", "you",
    "he", "she", "they", "we", "my", "your", "his", "her", "their", "our",
    "not", "no", "but", "if", "then", "than", "so", "as", "into", "about",
    "over", "after", "before", "up", "down", "out", "off", "very", "too",
    "also", "just", "only", "even", "again", "once", "here", "there",
}


def _script_detected(text: str) -> str | None:
    for code, rng in _INDIC_RANGES:
        if re.search("[" + rng + "]", text):
            return code
    return None


def detect_language(text: str) -> str:
    if not text:
        return "en"
    code = _script_detected(text)
    if code:
        return code
    for code, name in INDIAN_LANGUAGES.items():
        if code in text or name.lower() in text.lower():
            return code
    return "en"


class MultilingualTools:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, list[str]]] = {}

    @staticmethod
    def _clean_text(text: str) -> str:
        cleaned = []
        for ch in text:
            if ch in "*_~\t ":
                cleaned.append(" ")
            else:
                cleaned.append(ch)
        return re.sub(r"\s+", " ", "".join(cleaned)).strip()

    @staticmethod
    def _extract_keywords(text: str, language: str = "en") -> list[str]:
        if not text:
            return []
        cleaned = MultilingualTools._clean_text(text)
        cleaned = re.sub(r"[\u0900-\u097F]{1,2}", " ", cleaned)
        tokens = []
        for chunk in cleaned.split():
            token = chunk.strip("'-")
            if not token:
                continue
            lowered = token.lower()
            if language in {"hi", "mr", "bn", "te", "ta", "gu", "kn", "ml", "pa", "or"}:
                if re.fullmatch(r"[a-z0-9]+", lowered):
                    continue
                if lowered in _STOPWORDS:
                    continue
            else:
                if lowered in _STOPWORDS:
                    continue
            tokens.append(token)
        return tokens

    def detect(self, text: str) -> str:
        key = text[:500] if len(text) > 500 else text
        if key in self._cache:
            return self._cache[key][0]
        code = detect_language(text)
        self._cache[key] = (code, self._extract_keywords(text, code))
        return code

    def keywords(self, text: str, language: str | None = None) -> list[str]:
        code = language or detect_language(text)
        key = (code, text[:500])
        if key not in self._cache:
            self._cache[key] = (code, self._extract_keywords(text, code))
        return self._cache[key][1]

    def detect_or_extract(self, text: str) -> tuple[str, list[str]]:
        code = detect_language(text)
        return code, self._extract_keywords(text, code)
