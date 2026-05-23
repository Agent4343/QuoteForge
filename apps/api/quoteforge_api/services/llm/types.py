"""SDK-agnostic types for the Claude orchestration (§12).

The estimator loop is written against ``ClaudeClient`` and these normalized
blocks, so tests can inject a scripted fake with no network. The real adapter
(``client.py``) converts the Anthropic SDK response into these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

# Approximate claude-sonnet-4-5 pricing (USD per 1M tokens) and FX to CAD.
# Used only to record an estimated cost on LLMSession (§19); not billing-grade.
_USD_PER_MTOK_INPUT = Decimal("3")
_USD_PER_MTOK_OUTPUT = Decimal("15")
_USD_TO_CAD = Decimal("1.37")


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    content: list[TextBlock | ToolUseBlock]
    stop_reason: str  # "tool_use" | "end_turn" | ...
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.content if isinstance(b, TextBlock)).strip()


class ClaudeClient(Protocol):
    def create(
        self, *, system: list[dict], messages: list[dict], tools: list[dict]
    ) -> LLMResponse: ...


@dataclass
class GenerationResult:
    """Outcome of one /generate or /answer-question turn."""

    status: str  # "completed" | "question" | "error"
    question: dict | None = None  # {question, why_it_matters, affects_assemblies}
    assistant_text: str = ""
    error: str = ""
    flags: list[dict] = field(default_factory=list)


def estimate_cost_cad(input_tokens: int, output_tokens: int) -> Decimal:
    usd = (
        Decimal(input_tokens) / Decimal(1_000_000) * _USD_PER_MTOK_INPUT
        + Decimal(output_tokens) / Decimal(1_000_000) * _USD_PER_MTOK_OUTPUT
    )
    return (usd * _USD_TO_CAD).quantize(Decimal("0.0001"))
