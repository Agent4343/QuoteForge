# QuoteForge

AI-powered estimating for Canadian electrical contractors. A contractor
describes a job in plain language; QuoteForge produces an accurate, code-aware
estimate and a customer-ready proposal — and warns the contractor before they
underbid.

> Status: **backend complete; frontend pending.** The deterministic core
> (estimating engine, audit engine, tax engine, assembly library, price book),
> persistence, auth, the full quote lifecycle API, Claude-driven quote
> generation (§12), and bilingual WeasyPrint PDFs (§14) are built and tested.
> The React web frontend (§15) is the remaining major surface. See **Roadmap**.

## Architecture principles (non-negotiable, §3)

1. **The LLM never does math.** All numeric calculation is deterministic Python.
2. **Assemblies are the product.** The pricing/labour library is the moat.
3. **Province is a first-class dimension.** No "default Canada" mode.
4. **Code edition is tracked per quote** (esp. Quebec's CCÉ 2015 → 2021 transition).
5. **Profit protection blocks the PDF.** Critical audit flags must be overridden.
6. **No hallucinated code citations** — only verified `code_refs` from the library.
7. **French is professionally translated** for stored content, never LLM-translated.

## What is built (and tested)

| Area | Module | Tests |
|------|--------|-------|
| Money/Decimal primitives | `quoteforge_api/money.py` | — |
| Provinces | `quoteforge_api/provinces.py` | — |
| Provincial tax engine (§11) | `services/tax/` | `test_tax.py` |
| Material price book (§9.1) | `pricebook.py` + `data/pricebook/materials.json` | covered |
| Assembly schema + loader (§8) | `assemblies/` + `data/assemblies/*.yaml` | `test_assemblies.py` |
| Safe `qty_formula` evaluator | `services/estimating/formula.py` | `test_formula.py` |
| Permit lookup (§9.4) | `services/estimating/permits.py` | covered |
| **Estimating engine (§9)** | `services/estimating/` | `test_estimating.py` |
| **Audit engine (§10)** | `services/audit/` | `test_audit.py` |
| SQLAlchemy models + Alembic (§7) | `models/` + `alembic/` | covered |
| Auth: Argon2id, JWT, refresh rotation, reset (§16) | `auth/` | `test_app_flow.py` |
| Customer CRUD + per-user isolation (§13, §16) | `routes/customers.py` | `test_app_flow.py` |
| Quote CRUD + lifecycle + recompute/audit/override (§13) | `routes/quotes.py` + `services/quote_service.py` | `test_app_flow.py` |
| Dashboard stats (§13) | `routes/dashboard.py` | `test_app_flow.py` |
| **LLM orchestration (§12)** — Claude tool-use, ask/resume, question cap | `services/llm/` + `routes/quotes.py` | `test_llm.py` |
| **PDF generation (§14)** — EN/FR customer + internal, WeasyPrint, audit-gated | `services/pdf/` + `routes/quotes.py` | `test_app_flow.py` |
| Stateless preview API | `routes/estimate.py` + `schemas/` | `test_api.py` |

`69 tests` cover hand-verified reference estimates, provincial tax rules, the
full audit rule set, the §21 guarantee that a deliberately underbid quote is
**always** caught by a blocking critical flag, the end-to-end auth → customer →
quote lifecycle (cross-tenant isolation, refresh-token rotation), and the Claude
tool-use loop (with a scripted fake client — no network) including pause/resume
on `ask_contractor` and the rule that the engine, not the model, produces totals.

### LLM generation (§12)
`POST /api/quotes/{id}/generate` runs a synchronous Claude tool-use loop:
identify assemblies → `get_assembly_detail` → (`ask_contractor` if a
high-sensitivity parameter is unknown, max 4) → `compute_estimate` (the only path
to numbers) → `audit_estimate` → customer scope. A paused question is answered via
`POST /api/quotes/{id}/answer-question`. The system prompt caches the invariant
assembly index block. Requires `ANTHROPIC_API_KEY` (returns 503 without it).
Seeded assemblies are `draft`, so set `LLM_INCLUDE_DRAFT_ASSEMBLIES=true` in dev to
exercise the flow before electrician review.

## Running

### API tests / lint
```bash
cd apps/api
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
ruff check .
```

### Local stack (Postgres + API)
```bash
docker compose up --build
# API: http://localhost:8000/api/healthz
```

### Try the engine over HTTP
```bash
curl -s localhost:8000/api/estimate/preview -H 'content-type: application/json' -d '{
  "contractor": {"blended_labor_rate_cad": 110, "default_material_markup_pct": 35, "minimum_margin_pct": 20},
  "province": "ON", "code_edition": "OESC 2024 (28th)",
  "assemblies": [{"assembly_id": "circuit_new_15a_residential", "parameters": {"run_length_ft": 40, "access": "open"}}]
}' | jq
```

## Repo layout
```
apps/api/quoteforge_api/   FastAPI app + services (estimating, audit, tax, pdf, llm)
data/assemblies/           Version-controlled assembly YAML (the product)
data/pricebook/            Material price book JSON
Dockerfile, railway.json   Single-service production deploy (§18)
```

## Decisions made (from §23)
- Quote numbers: per-contractor, year-prefixed (`Q-2026-0001`).
- Quote validity: 30 days default.
- Logo storage: Railway volume.
- Multi-location contractors: out of scope for v1.

## Important caveats
- **Prices and labour hours are PLACEHOLDERS.** Per §9/§20/§21 they must be
  sourced from a supplier catalogue and reviewed by a licensed electrician before
  launch. The tests guard the engine *math*, not the business accuracy of inputs.
- **French strings are machine drafts** (`translation_status: draft`). Per §3.6
  and §21 they require professional review and a Quebec electrician's sign-off
  before customer-facing use. None are presented as final.
- All seeded assemblies are `status: draft`, so the (future) LLM index is empty
  until an electrician reviews them.

## Roadmap (per §20)
- [x] SQLAlchemy models + Alembic migrations (User, Customer, Quote, line items, audit flags, LLM sessions).
- [x] Auth (Argon2id, JWT access/refresh rotation, password reset) and per-user data isolation.
- [x] Full quote CRUD + lifecycle routes (§13), with engine-backed recompute and audit-gated send/finalize.
- [x] LLM orchestration with Claude tool-use (§12) — engine/audit/permits exposed as tools, prompt caching, ask/resume.
- [x] WeasyPrint PDF generation — EN/FR customer templates + internal breakdown (§14), audit-gated, `GET /quotes/{id}/pdf?variant=customer|internal`.
- [ ] React + Vite frontend (quote builder, dashboard, settings) (§15).
- [ ] Professional French translation + Quebec electrician review of the library.
- [ ] Expand the assembly library to the full ~50 (§8) and price book to ~200 SKUs.
- [ ] Logo upload to the Railway volume + `/auth/*` and `/quotes/*/generate` rate limiting on the generate route.
