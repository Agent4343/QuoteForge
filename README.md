# QuoteForge

AI-powered estimating for Canadian electrical contractors. A contractor
describes a job in plain language; QuoteForge produces an accurate, code-aware
estimate and a customer-ready proposal — and warns the contractor before they
underbid.

> Status: **foundation in progress.** The deterministic core (estimating
> engine, audit engine, tax engine, assembly library, price book) is built and
> fully tested. The LLM, persistence/auth, PDF generation, and web frontend are
> scaffolded but not yet implemented. See **Roadmap** below.

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
| Stateless preview API | `routes/` + `schemas/` | `test_api.py` |

`55 tests` cover hand-verified reference estimates, provincial tax rules, the
full audit rule set, and the §21 guarantee that a deliberately underbid quote is
**always** caught by a blocking critical flag.

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

## Roadmap (remaining, per §20)
- [ ] SQLAlchemy models + Alembic migrations (User, Customer, Quote, line items, audit flags, LLM sessions).
- [ ] Auth (Argon2id, JWT access/refresh, password reset) and per-user data isolation.
- [ ] Full quote CRUD + lifecycle routes (§13).
- [ ] LLM orchestration with Claude tool-use (§12) — engine/audit exposed as tools.
- [ ] WeasyPrint PDF generation (EN/FR customer + internal templates, §14).
- [ ] React + Vite frontend (quote builder, dashboard, settings) (§15).
- [ ] Professional French translation + Quebec electrician review of the library.
- [ ] Expand the assembly library to the full ~50 (§8) and price book to ~200 SKUs.
