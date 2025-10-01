from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests import Response
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class SAPAICoreClientError(RuntimeError):
    pass


class SAPAICoreClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        auth_url: str,
        api_base: str,
        deployment_id: str,
        resource_group: str,
        scope: Optional[str],
        chat_completions_path: Optional[str] = None,
        request_timeout: float = 120.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url.rstrip("/")
        self.api_base = api_base.rstrip("/")
        self.deployment_id = deployment_id
        self.resource_group = resource_group
        self.scope = scope
        self.chat_completions_path = chat_completions_path or f"/v2/inference/deployments/{deployment_id}/chat/completions"
        self.request_timeout = request_timeout

        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _token_url(self) -> str:
        return f"{self.auth_url}/oauth/token"

    def _build_headers(self) -> Dict[str, str]:
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "AI-Resource-Group": self.resource_group,
        }

    def _chat_url(self) -> str:
        return urljoin(f"{self.api_base}/", self.chat_completions_path.lstrip("/"))

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 30:
            return self._token

        payload = {"grant_type": "client_credentials"}
        if self.scope:
            payload["scope"] = self.scope

        response = requests.post(
            self._token_url(),
            data=payload,
            auth=(self.client_id, self.client_secret),
            timeout=self.request_timeout,
        )
        if response.status_code != 200:
            raise SAPAICoreClientError(f"Token request failed: {response.status_code} {response.text}")

        body = response.json()
        token = body.get("access_token")
        if not token:
            raise SAPAICoreClientError("No access token in AI Core response")

        expires_in = float(body.get("expires_in", 600))
        self._token = token
        self._token_expiry = now + expires_in
        return token

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        retry=retry_if_exception_type((requests.RequestException, SAPAICoreClientError)),
    )
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> str:
        payload: Dict[str, Any] = {
            "deployment_id": self.deployment_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = requests.post(
            self._chat_url(),
            headers=self._build_headers(),
            json=payload,
            timeout=self.request_timeout,
        )
        self._raise_for_status(response)
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise SAPAICoreClientError("No choices returned from AI Core")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise SAPAICoreClientError("Empty response content from AI Core")
        return content

    @staticmethod
    def _raise_for_status(response: Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise SAPAICoreClientError(
                f"AI Core request failed: {response.status_code} {response.text}"
            ) from exc
