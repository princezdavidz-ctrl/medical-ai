from typing import Any
import json

import httpx

from app.ai.gateway import ModelUnavailable
from app.ai.contracts import AIModelRequest, AIModelResponse
from app.ai.token_usage import extract_token_usage


class LocalModelUnavailable(ModelUnavailable):
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
        max_response_chars: int = 50000,
        client: httpx.Client | None = None,
    ) -> None:
        if not 1 <= max_tokens <= 8192:
            raise ValueError("max_tokens_must_be_between_1_and_8192")
        if not 1000 <= max_response_chars <= 100000:
            raise ValueError("max_response_chars_must_be_between_1000_and_100000")
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.model_version = (
            f"{model_version}+sha256:{model_digest[:12]}"
            if model_digest else model_version
        )
        self.max_tokens = max_tokens
        self.max_response_chars = max_response_chars
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
        if not request.prompt.strip() or len(request.prompt) > 8000:
            raise LocalModelUnavailable("Prompt is empty or exceeds the configured input limit")
        if len(request.evidence_context) > 50000:
            raise LocalModelUnavailable("Evidence context exceeds the configured input limit")
        registry_contract = (
            "\\n\\nCAPABILITY-SPECIFIC SYSTEM INSTRUCTIONS:\\n"
            + request.system_prompt
            + "\\n\\nOUTPUT CONTRACT (metadata for the response envelope):\\n"
            + json.dumps(request.output_schema or {}, sort_keys=True)
            + "\\n\\nWORKFLOW SAFETY CONTRACT:\\n"
            + json.dumps(request.workflow_contract or {}, sort_keys=True)
            + "\\n\\nPERMITTED TOOLS: "
            + json.dumps(request.tool_permissions)
            + ". No tools are enabled unless explicitly listed.\\n\\n"
        )
        system_message = (
            "You are a medical information and clinical decision-support assistant. "
            "Do not issue autonomous diagnoses, prescriptions, orders or treatment decisions. "
            "Follow the capability-specific system instructions and workflow safety contract. "
            "Cite exact supplied evidence tokens and state uncertainty.\\n\\n"
            + registry_contract
            + request.evidence_context
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0,
            "max_tokens": min(self.max_tokens, request.max_output_tokens),
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
        if len(content) > self.max_response_chars:
            raise LocalModelUnavailable("Local model response exceeds the configured output limit")

        prompt_tokens, completion_tokens, total_tokens, usage_is_estimated = extract_token_usage(
            body,
            prompt_text=system_message + request.prompt,
            completion_text=content,
        )
        return AIModelResponse(
            content=content.strip(),
            provider=self.provider_id,
            model=self.model_name,
            model_version=self.model_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_is_estimated=usage_is_estimated,
        )
