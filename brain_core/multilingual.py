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


def detect_language(text: str) -> str:
    """Detect the dominant Indian language of text; falls back to en."""
    if not text:
        return "en"
    for code, name in INDIAN_LANGUAGES.items():
        if code in text or name in text:
            return code
    return "en"


class MultilingualTools:
    """Unicode-safe keyword extraction tuned for Indian-language content."""

    WILDCARD_PATTERN = re.compile(r"[\s_*]{2,}|[^\w\s\-'’]|[\u0900-\u097F]{1,2}")

    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, list[str]]] = {}

    def detect(self, text: str) -> str:
        key = text[:500] if len(text) > 500 else text
        if key in self._cache:
            return self._cache[key][0]
        code = detect_language(text)
        self._cache[key] = (code, self._extract_keywords(text, code))
        return code

    @staticmethod
    def _extract_keywords(text: str, language: str = "en") -> list[str]:
        if not text:
            return []
        cleaned = re.sub(r"[^\w\s\-'’]", " ", text)
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

    def keywords(self, text: str, language: str | None = None) -> list[str]:
        code = language or detect_language(text)
        key = (code, text[:500])
        if key not in self._cache:
            self._cache[key] = (code, self._extract_keywords(text, code))
        return self._cache[key][1]

    def detect_or_extract(self, text: str) -> tuple[str, list[str]]:
        code = detect_language(text)
        return code, self._extract_keywords(text, code)
