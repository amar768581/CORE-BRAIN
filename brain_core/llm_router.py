from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

GROQ_BASE = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-2.5-flash"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"


class ZeroBudgetLLMRouter:
    def __init__(self, timeout: float = 20.0, max_rotate: int = 3) -> None:
        self.timeout = timeout
        self.max_rotate = max_rotate
        self._groq_keys: list[str] = self._load_keys("GROQ_API_KEY")
        self._gemini_keys: list[str] = self._load_keys("GEMINI_API_KEY")
        self._groq_index = 0
        self._gemini_index = 0
        self.last_error: Optional[str] = None

    @staticmethod
    def _load_keys(env_var: str) -> list[str]:
        values = os.environ.get(env_var)
        if not values:
            return []
        return [v.strip() for v in values.split(",") if v.strip()]

    @property
    def engines(self) -> list[str]:
        engines = []
        if self._groq_keys:
            engines.append("groq")
        if self._gemini_keys:
            engines.append("gemini")
        if not engines:
            engines.append(None)
        return engines

    def generate_json(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        if self._groq_keys:
            result = self._route_groq(system_prompt, user_prompt)
            if result is not None:
                return result
        if self._gemini_keys:
            result = self._route_gemini(system_prompt, user_prompt)
            if result is not None:
                return result
        self.last_error = "No LLM key available: falling back to rule-based logic"
        return None

    def _route_groq(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        for _ in range(min(self.max_rotate, len(self._groq_keys))):
            key = self._groq_keys[self._groq_index % len(self._groq_keys)]
            self._groq_index += 1
            payload = {
                "model": GROQ_DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            try:
                response = self._post_json(GROQ_BASE, headers, payload)
                content = response["choices"][0]["message"]["content"]
                parsed = self._extract_json(content)
                if parsed is not None:
                    return parsed
                self.last_error = "Groq returned non-JSON output"
            except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                    KeyError, IndexError, TypeError) as exc:
                self.last_error = f"Groq call failed: {exc}"
            time.sleep(0.05)
        return None

    def _route_gemini(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        for _ in range(min(self.max_rotate, len(self._gemini_keys))):
            key = self._gemini_keys[self._gemini_index % len(self._gemini_keys)]
            self._gemini_index += 1
            url = f"{GEMINI_BASE}/{GEMINI_MODEL}:generateContent?key={key}"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            }
            headers = {"Content-Type": "application/json"}
            try:
                response = self._post_json(url, headers, payload)
                text = response["candidates"][0]["content"]["parts"][0]["text"]
                parsed = self._extract_json(text)
                if parsed is not None:
                    return parsed
                self.last_error = "Gemini returned non-JSON output"
            except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                    KeyError, IndexError, TypeError) as exc:
                self.last_error = f"Gemini call failed: {exc}"
            time.sleep(0.05)
        return None

    def _post_json(self, url: str, headers: dict, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_json(text: Any) -> Optional[dict]:
        if not isinstance(text, str) or not text.strip():
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
            newline = cleaned.find("\n")
            if newline != -1:
                cleaned = cleaned[newline + 1:]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3]
            cleaned = cleaned.strip()
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None
