"""Token usage extraction with conservative character-based estimates."""
from typing import Any


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def extract_token_usage(
    body: Any, *, prompt_text: str, completion_text: str
) -> tuple[int, int, int, bool]:
    usage = body.get("usage") if isinstance(body, dict) else None
    prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    actual_usage = (
        isinstance(prompt_tokens, int)
        and not isinstance(prompt_tokens, bool)
        and prompt_tokens >= 0
        and isinstance(completion_tokens, int)
        and not isinstance(completion_tokens, bool)
        and completion_tokens >= 0
    )
    if actual_usage:
        return (
            prompt_tokens,
            completion_tokens,
            prompt_tokens + completion_tokens,
            False,
        )
    estimated_prompt = estimate_tokens(prompt_text)
    estimated_completion = estimate_tokens(completion_text)
    return (
        estimated_prompt,
        estimated_completion,
        estimated_prompt + estimated_completion,
        True,
    )
