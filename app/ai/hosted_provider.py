"""Explicitly configured hosted OpenAI-compatible provider.

This provider accepts only HTTPS endpoints and is never selected for patient-context,
offline or degraded requests. Cross-provider fallback is handled by no component.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.ai.contracts import AIModelRequest, AIModelResponse, OperatingMode
from app.ai.gateway import ModelUnavailable


class HostedModelUnavailable(ModelUnavailable):
    pass


class HostedOpenAICompatibleProvider:
    provider_id = "hosted-openai-compatible"
    provider_class = "hosted"

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        model_version: str,
        api_key: str,
        timeout_seconds: float = 45.0,
        max_tokens: int = 1200,
        max_response_chars: int = 50000,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("hosted_provider_requires_https")
        if not api_key.strip() or not model_name.strip() or not model_version.strip():
            raise ValueError("hosted_provider_identity_and_secret_required")
        if not 1 <= max_tokens <= 8192:
            raise ValueError("max_tokens_must_be_between_1_and_8192")
        if not 1000 <= max_response_chars <= 100000:
            raise ValueError("max_response_chars_must_be_between_1000_and_100000")
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.model_version = model_version
        self.max_tokens = max_tokens
        self.max_response_chars = max_response_chars
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_seconds))
        self._owns_client = client is None
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def health_check(self) -> bool:
        try:
            response = self._client.get(f"{self.base_url}/v1/models", headers=self._headers)
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
        if request.operating_mode is not OperatingMode.HYBRID:
            raise HostedModelUnavailable("hosted_provider_forbidden_outside_hybrid_mode")
        if not request.prompt.strip() or len(request.prompt) > 8000:
            raise HostedModelUnavailable("prompt_empty_or_exceeds_limit")
        if len(request.evidence_context) > 50000:
            raise HostedModelUnavailable("evidence_context_exceeds_limit")

        system_message = (
            "You are a medical information assistant using approved public medical evidence. "
            "You are not a doctor and must not issue autonomous diagnoses, prescriptions, "
            "orders or treatment decisions. Cite exact citation tokens, state uncertainty, "
            "and identify evidence gaps. Do not infer patient identity or personal details.\n\n"
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
            raise HostedModelUnavailable("configured_hosted_model_request_failed") from exc

        if not isinstance(body, dict):
            raise HostedModelUnavailable("hosted_model_invalid_response_envelope")
        choices = body.get("choices")
        if body.get("model") != self.model_name or not isinstance(choices, list) or not choices:
            raise HostedModelUnavailable("hosted_model_identity_or_response_shape_mismatch")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise HostedModelUnavailable("hosted_model_returned_no_content")
        if len(content) > self.max_response_chars:
            raise HostedModelUnavailable("hosted_model_response_exceeds_limit")

        return AIModelResponse(
            content=content.strip(),
            provider=self.provider_id,
            model=self.model_name,
            model_version=self.model_version,
        )
