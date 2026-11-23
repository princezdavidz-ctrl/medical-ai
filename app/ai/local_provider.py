from typing import Any

import httpx

from app.ai.contracts import AIModelRequest, AIModelResponse


class LocalModelUnavailable(RuntimeError):
    pass


class LocalOpenAICompatibleProvider:
    """Local-only OpenAI-compatible chat provider; never routes to hosted services."""

    provider_id = "local-openai-compatible"
    provider_class = "local"

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        model_version: str,
        model_digest: str | None = None,
        timeout_seconds: float = 45.0,
        max_tokens: int = 1200,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.model_version = (
            f"{model_version}+sha256:{model_digest[:12]}"
            if model_digest else model_version
        )
        self.max_tokens = max_tokens
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_seconds))
        self._owns_client = client is None
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def health_check(self) -> bool:
        try:
            response = self._client.get(
                f"{self.base_url}/v1/models", headers=self._headers
            )
            response.raise_for_status()
            payload: Any = response.json()
            models = payload.get("data", []) if isinstance(payload, dict) else []
            return any(
                isinstance(item, dict) and item.get("id") == self.model_name
                for item in models
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    def generate(self, request: AIModelRequest) -> AIModelResponse:
        system_message = (
            "You are a medical information and clinical decision-support assistant. "
            "You are not a doctor and must not issue autonomous diagnoses, prescriptions, "
            "orders, or treatment decisions. Follow the evidence policy and cite the exact "
            "citation tokens supplied. State uncertainty and evidence gaps clearly.\n\n"
            + request.evidence_context
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        try:
            response = self._client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            body: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalModelUnavailable("Configured local model runtime request failed") from exc

        if not isinstance(body, dict):
            raise LocalModelUnavailable("Local model returned an invalid response envelope")
        reported_model = body.get("model")
        choices = body.get("choices")
        if reported_model != self.model_name or not isinstance(choices, list) or not choices:
            raise LocalModelUnavailable("Local model identity or response shape did not match configuration")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LocalModelUnavailable("Local model returned no usable response content")

        return AIModelResponse(
            content=content.strip(),
            provider=self.provider_id,
            model=self.model_name,
            model_version=self.model_version,
        )
