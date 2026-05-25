"""Proposal quality layer (§24): scope-prose guidance in the system prompt and
clean paragraph rendering in the customer PDF."""

from __future__ import annotations

from quoteforge_api.models import Customer, Quote, QuoteLineItem, User
from quoteforge_api.models.enums import Language, LineSource
from quoteforge_api.provinces import Province
from quoteforge_api.services.llm.system_prompt import build_system
from quoteforge_api.services.pdf.renderer import _paragraphs
from quoteforge_api.services.quote_service import ensure_terminology_flag


def _models() -> tuple[User, Customer, Quote]:
    user = User(full_name="Sam Sparks", business_name="Sparks Electric", province=Province.ON)
    customer = Customer(name="Jane", province=Province.ON)
    quote = Quote(province=Province.ON, code_edition="OESC 2024 (28th)", customer_language=Language.EN)
    return user, customer, quote


def test_system_prompt_carries_proposal_quality_guidance():
    user, customer, quote = _models()
    blocks = build_system(user, customer, quote, index=[])
    invariant = blocks[0]["text"]
    # Lives in the cached (invariant) block so every quote gets it for free.
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    # Tone (§24.1)
    assert "premium residential electrical contractor" in invariant
    # Terminology enforcement (§24.2)
    assert "garage feeder" in invariant
    assert "garage distribution panel" in invariant
    # Required vs optional + trust framing (§24.4)
    assert "REQUIRED work" in invariant
    assert "RECOMMENDED / OPTIONAL" in invariant
    assert "supports future EV charging" in invariant


def _quote_with(assembly_id: str, scope_en: str) -> Quote:
    return Quote(
        province=Province.ON, customer_language=Language.EN,
        customer_facing_scope_en=scope_en, audit_flags=[],
        line_items=[QuoteLineItem(
            line_number=1, source=LineSource.ASSEMBLY, assembly_id=assembly_id,
            description_en="x", description_fr="x", is_optional=False,
        )],
    )


def test_finalize_terminology_lint_appends_flag():
    # Feeder/subpanel work described as a "new service" -> warn flag at finalize.
    quote = _quote_with("subpanel_60a", "Install a new electrical service to the garage.")
    ensure_terminology_flag(quote)
    codes = [f.code for f in quote.audit_flags]
    assert "TERMINOLOGY_SERVICE_MISUSE" in codes
    # Idempotent: a second pass doesn't duplicate the flag.
    ensure_terminology_flag(quote)
    assert codes.count("TERMINOLOGY_SERVICE_MISUSE") == len(
        [f for f in quote.audit_flags if f.code == "TERMINOLOGY_SERVICE_MISUSE"]
    ) == 1


def test_finalize_terminology_lint_silent_for_real_service_upgrade():
    quote = _quote_with("service_upgrade_200a_overhead", "Upgrade the service to 200A.")
    ensure_terminology_flag(quote)
    assert [f.code for f in quote.audit_flags] == []


def test_scope_paragraph_split():
    assert _paragraphs(None) == []
    assert _paragraphs("") == []
    assert _paragraphs("one block") == ["one block"]
    assert _paragraphs("required work\n\noptional upgrade") == ["required work", "optional upgrade"]
    # Collapses extra blank lines and trims surrounding whitespace.
    assert _paragraphs("a\n\n\n\nb") == ["a", "b"]
    assert _paragraphs("  \n\n keep me \n\n ") == ["keep me"]
