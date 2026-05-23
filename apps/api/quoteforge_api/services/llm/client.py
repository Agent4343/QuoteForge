"""Anthropic SDK adapter (§12). Converts SDK responses to normalized blocks.

A single provider — Claude — is intentional (§5: no multi-provider abstraction).
The thin ``ClaudeClient`` protocol exists only so tests can run without network.
"""

from __future__ import annotations

from quoteforge_api.config import get_settings
from quoteforge_api.services.llm.types import LLMResponse, TextBlock, ToolUseBlock


class AnthropicClient:
    def __init__(self, api_key: str, model: str, max_tokens: int = 4096):
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def create(self, *, system: list[dict], messages: list[dict], tools: list[dict]) -> LLMResponse:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        content: list[TextBlock | ToolUseBlock] = []
        for block in resp.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(ToolUseBlock(id=block.id, name=block.name, input=dict(block.input)))
        usage = resp.usage
        return LLMResponse(
            content=content,
            stop_reason=resp.stop_reason or "end_turn",
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
        )


def get_client() -> AnthropicClient:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)
