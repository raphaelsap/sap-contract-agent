from __future__ import annotations

from typing import Any, Dict, List

import requests


class OpenAIClientError(RuntimeError):
    """Raised when the OpenAI API returns an error."""


class OpenAIChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        request_timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required to use the contract agent.")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.request_timeout = request_timeout

    def _chat_url(self) -> str:
        return f"{self.api_base}/chat/completions"

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.2,
        max_completion_tokens: int = 900,
        top_p: float = 1.0,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "top_p": top_p,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            self._chat_url(),
            json=payload,
            headers=headers,
            timeout=self.request_timeout,
        )
        if response.status_code != 200:
            raise OpenAIClientError(
                f"OpenAI request failed: {response.status_code} {response.text}"
            )
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise OpenAIClientError("OpenAI response did not contain choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise OpenAIClientError("OpenAI response did not contain message content")
        return content
