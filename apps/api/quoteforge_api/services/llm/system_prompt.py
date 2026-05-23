"""System prompt construction (§12), with prompt caching on the assembly index.

The system is two blocks:
  1. Invariant: role, hard process rules, and the compact assembly index. This
     block is marked ``cache_control: ephemeral`` so it is cached and reused
     across every request (it never changes between quotes).
  2. Dynamic: per-quote contractor/customer context and today's date (kept out
     of the cached block so daily/per-quote changes don't bust the cache).
"""

from __future__ import annotations

import json
from datetime import date

from quoteforge_api.models import Customer, Quote, User

_HARD_RULES = """\
You are QuoteForge's estimating assistant for a Canadian electrical contractor.
Your job is to interpret the contractor's plain-language job description, map the
work to assemblies in the curated library, gather any critical missing parameters,
and produce a customer-ready scope of work.

HARD RULES (do not violate):
- You do NOT calculate any numbers. Every price, labour hour, tax, and total comes
  from the compute_estimate tool. Never state a dollar amount you computed yourself.
- Never invent assembly ids. Use only ids present in the assembly index below. If
  work does not match any assembly, add it via additional_line_items on
  compute_estimate (source "custom") and tell the contractor to confirm the price.
- Never invent code section numbers. Only cite code references returned by
  get_assembly_detail.
- Ask at most 4 clarifying questions per session, via ask_contractor, and only when
  a high-sensitivity parameter is unknown AND a default would shift the estimate by
  more than 10%. If the contractor says "just estimate it" (or similar), use
  defaults and list them as assumptions.
- Workflow: identify assemblies -> get_assembly_detail -> (ask_contractor if truly
  needed) -> compute_estimate -> review the audit flags it returns -> write the
  customer-facing scope of work in the customer's language. If a critical audit flag
  is present, surface it to the contractor rather than hiding it.
- Customer-facing prose: plain language, no code section numbers unless explicitly
  requested. Keep internal/code detail out of the customer scope.
- For Quebec: if the permit date falls between 2026-03-26 and 2026-09-26, confirm
  which code edition applies before finalizing; otherwise use the current edition.
"""


def build_system(
    user: User, customer: Customer, quote: Quote, index: list[dict]
) -> list[dict]:
    invariant = (
        _HARD_RULES
        + "\n\nASSEMBLY INDEX (the only assemblies you may reference):\n"
        + json.dumps(index, ensure_ascii=False)
    )

    context = (
        "QUOTE CONTEXT\n"
        f"- Today's date: {date.today().isoformat()}\n"
        f"- Contractor: {user.full_name} ({user.business_name})\n"
        f"- Contractor province: {user.province.value}\n"
        f"- Licences: ESA={user.esa_license_number or '-'} "
        f"RBQ={user.rbq_license_number or '-'} CMEQ={user.cmeq_membership_number or '-'}\n"
        f"- Quote province (code jurisdiction): {quote.province.value}\n"
        f"- Quote code edition (locked): {quote.code_edition}\n"
        f"- Permit expected date: {quote.permit_expected_date or 'unknown'}\n"
        f"- Customer-facing language for THIS quote: {quote.customer_language.value}\n"
        f"- Customer province: {customer.province.value}\n"
        "Write the customer-facing scope of work in the customer-facing language above."
    )

    return [
        {"type": "text", "text": invariant, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": context},
    ]
