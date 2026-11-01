"""LLMClient: zero-dependency LLM access (Groq + Gemini) with safe fallback.

Uses only the Python standard library (urllib.request, json, os) - no pip
packages required. Reads GROQ_API_KEY / GEMINI_API_KEY from the environment:
Groq's OpenAI-compatible chat completions endpoint is preferred when its key
is set, otherwise Gemini's REST endpoint is used. When neither key is
configured - or any call, network request or parse fails - generate_json
returns None so callers can seamlessly fall back to rule-based logic.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


class LLMClient:
    """Tiny stdlib-only chat client returning parsed JSON objects (or None)."""

    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.3-70b-versatile"
    GEMINI_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.last_error: Optional[str] = None

    @property
    def engine(self) -> Optional[str]:
        """Provider that would serve a request: \"groq\", \"gemini\" or None."""
        if self.groq_api_key:
            return "groq"
        if self.gemini_api_key:
            return "gemini"
        return None

    def available(self) -> bool:
        """True when at least one provider API key is configured."""
        return self.engine is not None

    @staticmethod
    def _extract_json(text: Any) -> Optional[dict]:
        """Safely parse a JSON object from model output (code fences tolerated)."""
        if not isinstance(text, str) or not text.strip():
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
            newline = cleaned.find("\n")
            if newline != -1:  # drop the optional "json" fence label
                cleaned = cleaned[newline + 1:]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3]
            cleaned = cleaned.strip()
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _post_json(self, url: str, headers: dict, payload: dict) -> dict:
        """POST a JSON payload and parse the JSON response (stdlib only)."""
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def generate_json(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        """Return a JSON object from the configured provider, else None.

        Groq is used when GROQ_API_KEY is set, otherwise Gemini when
        GEMINI_API_KEY is set. Missing keys, network errors, HTTP errors and
        invalid JSON all yield None (recorded in ``last_error``) so callers
        can fall back to deterministic rule-based logic.
        """
        if self.groq_api_key:
            return self._generate_groq(system_prompt, user_prompt)
        if self.gemini_api_key:
            return self._generate_gemini(system_prompt, user_prompt)
        return None  # No key configured: caller falls back to rule-based logic.

    def _generate_groq(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        payload = {
            "model": self.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self._post_json(self.GROQ_URL, headers, payload)
            content = response["choices"][0]["message"]["content"]
            parsed = self._extract_json(content)
            self.last_error = None if parsed is not None else "Groq returned non-JSON output"
            return parsed
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, IndexError, TypeError) as exc:
            self.last_error = f"Groq call failed: {exc}"
            return None

    def _generate_gemini(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }
        headers = {"Content-Type": "application/json"}
        url = f"{self.GEMINI_URL}?key={self.gemini_api_key}"
        try:
            response = self._post_json(url, headers, payload)
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            parsed = self._extract_json(text)
            self.last_error = None if parsed is not None else "Gemini returned non-JSON output"
            return parsed
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, IndexError, TypeError) as exc:
            self.last_error = f"Gemini call failed: {exc}"
            return None


if __name__ == "__main__":
    # Smoke test with a mocked _post_json transport - no real keys, no network.
    _KEY_ENV = ("GROQ_API_KEY", "GEMINI_API_KEY")
    _saved = {key: os.environ.pop(key, None) for key in _KEY_ENV}

    try:
        # --- No keys configured: None, no call attempted -------------------
        client = LLMClient()
        assert client.engine is None and not client.available()
        assert client.generate_json("sys", "user") is None

        # --- Groq happy path (mocked response) -----------------------------
        os.environ["GROQ_API_KEY"] = "gsk_test"
        os.environ["GEMINI_API_KEY"] = "gem_test"
        groq_client = LLMClient()
        assert groq_client.engine == "groq"  # Groq wins when both keys exist

        calls = []

        def _groq_ok(url, headers, payload):
            calls.append((url, headers, payload))
            return {"choices": [{"message": {"content": '```json\n{"answer": 42}\n```'}}]}

        groq_client._post_json = _groq_ok
        assert groq_client.generate_json("sys", "user") == {"answer": 42}
        assert groq_client.last_error is None
        url, headers, payload = calls[0]
        assert url == LLMClient.GROQ_URL
        assert headers["Authorization"] == "Bearer gsk_test"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["messages"][0] == {"role": "system", "content": "sys"}

        # --- Groq failures: invalid JSON and network error -> None ---------
        groq_client._post_json = lambda *a, **k: {"choices": [{"message": {"content": "not json {"}}]}
        assert groq_client.generate_json("sys", "user") is None
        assert groq_client.last_error

        def _boom(*args, **kwargs):
            raise urllib.error.URLError("connection refused")

        groq_client._post_json = _boom
        assert groq_client.generate_json("sys", "user") is None
        assert "connection refused" in groq_client.last_error

        # --- Gemini path when only the Gemini key exists -------------------
        os.environ.pop("GROQ_API_KEY", None)
        gemini_client = LLMClient()
        assert gemini_client.engine == "gemini"

        def _gemini_ok(url, headers, payload):
            assert "?key=" in url
            assert payload["generationConfig"]["responseMimeType"] == "application/json"
            return {"candidates": [{"content": {"parts": [{"text": '{"hello": "gemini"}'}]}}]}

        gemini_client._post_json = _gemini_ok
        assert gemini_client.generate_json("sys", "user") == {"hello": "gemini"}
        assert gemini_client.last_error is None

        # --- _extract_json edge cases --------------------------------------
        extract = LLMClient._extract_json
        assert extract('{"a": 1}') == {"a": 1}
        assert extract('```json\n{"a": 1}\n```') == {"a": 1}
        assert extract("[1, 2]") is None  # only JSON objects are accepted
        assert extract("plain prose") is None
        assert extract(None) is None

        print("LLMClient smoke test passed (mocked Groq + Gemini, no network).")
    finally:
        for key, value in _saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
