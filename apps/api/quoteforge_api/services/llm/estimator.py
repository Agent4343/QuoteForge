"""Claude estimating orchestration (§12).

Drives the tool-use conversation: identify assemblies -> get detail -> (ask the
contractor if truly needed) -> compute_estimate -> audit -> write the customer
scope. The loop is synchronous (a quote generation is one blocking request, per
§12) and SDK-agnostic via the ClaudeClient protocol.

State lives on the quote's LLMSession (full message history + tool calls +
token/cost accounting, per §12/§19), so a paused ask_contractor can be resumed.
"""

from __future__ import annotations

import json

from quoteforge_api.config import get_settings
from quoteforge_api.models import LLMSession, Quote
from quoteforge_api.models.enums import Language
from quoteforge_api.services.llm.system_prompt import build_system
from quoteforge_api.services.llm.tools import ASK_CONTRACTOR, TOOL_DEFS, ToolContext, execute_tool
from quoteforge_api.services.llm.types import (
    ClaudeClient,
    GenerationResult,
    LLMResponse,
    TextBlock,
    ToolUseBlock,
    estimate_cost_cad,
)


def _to_wire(blocks: list[TextBlock | ToolUseBlock]) -> list[dict]:
    wire: list[dict] = []
    for b in blocks:
        if isinstance(b, TextBlock):
            wire.append({"type": "text", "text": b.text})
        else:
            wire.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return wire


def _count_questions(messages: list[dict]) -> int:
    n = 0
    for m in messages:
        if m.get("role") != "assistant":
            continue
        for block in m.get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use" \
                    and block.get("name") == ASK_CONTRACTOR:
                n += 1
    return n


def _record_usage(session: LLMSession, resp: LLMResponse) -> None:
    session.input_tokens += resp.input_tokens
    session.output_tokens += resp.output_tokens
    session.cost_cad = estimate_cost_cad(session.input_tokens, session.output_tokens)


def _store_scope(quote: Quote, text: str) -> None:
    if not text:
        return
    if quote.customer_language == Language.FR:
        quote.customer_facing_scope_fr = text
    else:
        quote.customer_facing_scope_en = text


def _run_loop(ctx: ToolContext, client: ClaudeClient, session: LLMSession,
              messages: list[dict]) -> GenerationResult:
    settings = get_settings()
    index = ctx.library.llm_index(include_draft=ctx.include_draft)
    system = build_system(ctx.user, ctx.customer, ctx.quote, index)
    tool_log: list[dict] = list(session.tool_calls or [])

    for _ in range(settings.llm_max_tool_turns):
        resp = client.create(system=system, messages=messages, tools=TOOL_DEFS)
        _record_usage(session, resp)
        messages.append({"role": "assistant", "content": _to_wire(resp.content)})

        if resp.stop_reason != "tool_use":
            session.messages = messages
            session.tool_calls = tool_log
            _store_scope(ctx.quote, resp.text)
            return GenerationResult(
                status="completed",
                assistant_text=resp.text,
                flags=[{"severity": f.severity.value, "code": f.code,
                        "message_en": f.message_en} for f in ctx.quote.audit_flags],
            )

        tool_uses = resp.tool_uses
        ask = next((t for t in tool_uses if t.name == ASK_CONTRACTOR), None)
        cap_reached = _count_questions(messages) > settings.llm_max_questions

        if ask is not None and not cap_reached:
            session.messages = messages
            session.tool_calls = tool_log
            return GenerationResult(status="question", question=ask.input)

        # Execute every tool_use; for ask past the cap, inject a "use defaults" answer.
        results: list[dict] = []
        for t in tool_uses:
            if t.name == ASK_CONTRACTOR:
                out: dict | str = (
                    "Question limit reached. Use sensible defaults and list them as "
                    "assumptions; do not ask further questions."
                )
            else:
                out = execute_tool(ctx, t.name, t.input)
                tool_log.append({"name": t.name, "input": t.input, "result": out})
            results.append({
                "type": "tool_result",
                "tool_use_id": t.id,
                "content": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": results})

    session.messages = messages
    session.tool_calls = tool_log
    return GenerationResult(status="error", error="Tool-use turn limit reached without completion.")


def start_generation(ctx: ToolContext, client: ClaudeClient, session: LLMSession,
                     job_description: str) -> GenerationResult:
    messages = list(session.messages or [])
    messages.append({"role": "user", "content": job_description})
    return _run_loop(ctx, client, session, messages)


def continue_generation(ctx: ToolContext, client: ClaudeClient, session: LLMSession,
                        answer: str) -> GenerationResult:
    """Resume a paused session by answering the outstanding ask_contractor.

    Provides tool_result blocks for every tool_use in the last assistant turn
    (the answer for ask_contractor, executed results for any others).
    """
    messages = list(session.messages or [])
    if not messages or messages[-1].get("role") != "assistant":
        return GenerationResult(status="error", error="No pending question to answer.")

    tool_log: list[dict] = list(session.tool_calls or [])
    results: list[dict] = []
    for block in messages[-1].get("content", []):
        if not (isinstance(block, dict) and block.get("type") == "tool_use"):
            continue
        if block.get("name") == ASK_CONTRACTOR:
            out: dict | str = answer
        else:
            out = execute_tool(ctx, block["name"], block.get("input", {}))
            tool_log.append({"name": block["name"], "input": block.get("input"), "result": out})
        results.append({
            "type": "tool_result",
            "tool_use_id": block["id"],
            "content": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False),
        })
    if not results:
        return GenerationResult(status="error", error="No pending question to answer.")
    messages.append({"role": "user", "content": results})
    session.tool_calls = tool_log
    return _run_loop(ctx, client, session, messages)
