"""LLM generation request/response schemas (§12, §13)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from quoteforge_api.schemas.quote import QuoteOut


class GenerateRequest(BaseModel):
    # Defaults to the quote's stored job_description if omitted.
    job_description: str | None = Field(default=None, max_length=4000)


class AnswerQuestionRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class GenerationResponse(BaseModel):
    status: str  # completed | question | error
    question: dict | None = None
    assistant_text: str = ""
    error: str = ""
    quote: QuoteOut
