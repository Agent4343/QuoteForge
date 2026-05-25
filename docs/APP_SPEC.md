# QuoteForge — Live App Spec (As-Built)

> **This is the *current-state* rebuild prompt.** It describes QuoteForge as it actually exists in this repository today, not the original v1 plan. The founding spec is preserved verbatim in `docs/BUILD_PROMPT.md`; where the two differ, **this file wins** for "what the code does."
>
> Use it with Claude Code, Cursor, or any agentic tool to understand, extend, or rebuild the app. It remains intentionally opinionated and scope-limited — do not expand scope without explicit instruction.

> **Status banner (read before trusting any number).** The estimating *machinery* is real and tested, but the *data* is not production-ready: all **49 assemblies are `status: draft`** (zero electrician-reviewed), the price book has **68 SKUs** (placeholder costs), and stored French is **machine-drafted pending professional review**. No live in-browser E2E pass has been run in CI yet (Chromium download is blocked in the build sandbox). Treat outputs as structurally correct but not field-accurate until a licensed electrician signs off.

-----

## 1. Project Identity

**Name:** QuoteForge
**Tagline:** AI-powered estimating for Canadian electrical contractors.
**Audience:** Licensed electrical contractors in Canada (Ontario and Quebec at launch; data + schema support all ten provinces).
**Built by:** Solo founder. Optimize for one person maintaining the entire stack.

## 2. The One-Sentence Pitch

A contractor describes a job in plain language (typed); QuoteForge produces an accurate, code-aware estimate and a customer-ready proposal in minutes, warns the contractor before they underbid, and lets them keep refining it by chatting with the AI.

## 3. Non-Negotiable Architectural Principles

Unchanged from v1, still enforced in code:

1. **The LLM never does math.** All numbers come from the deterministic Python engine (`compute_estimate`). The model interprets language and maps work to assemblies; if it ever emits a price, that's a bug.
2. **Assemblies are the product.** The pricing/labour library is the moat — version-controlled YAML in git, reviewed on every change. The UI and AI wrap it. (Still true: assemblies are NOT in the DB; loaded into memory at startup.)
3. **Province is a first-class dimension.** Every assembly, tax calc, permit lookup, code lookup, and PDF knows the province. No "default Canada."
4. **Code edition is tracked per quote.** The quote stores the edition in force at quote time. Quebec's CCÉ 2015→2021 transition window (2026-03-26 → 2026-09-26) is modelled in the code matrix.
5. **Profit protection gates the PDF.** Every estimate runs the audit pass; **critical** flags block customer-PDF generation/sending until the contractor explicitly overrides (logged with timestamp).
6. **No hallucinated code citations.** Customer/internal docs cite only verified `code_refs` from the assembly data.
7. **French is professionally translated for stored content, never LLM-translated.** LLM French is allowed only for the customer-facing prose written at quote time. Machine-drafted French in data is flagged pending review.
8. **No offline mode.** Mobile-responsive web app, fully online.

## 4. What the app IS (current)

- Web app, mobile-responsive, served as a single Railway service (FastAPI serves `/api/*` + the built React SPA).
- One trade: electrical. Ten provinces in the data; ON/QC are the focus.
- **49 assemblies** (all `status: draft`), **68-SKU** price book.
- AI quote generation from typed text, as a **continuous refinement chat** (not a one-shot flow).
- Deterministic estimating engine (materials, labour, permits, tax, markup, margin).
- Profit-protection audit pass with PDF gating + override.
- Bilingual (EN/FR) customer + internal PDFs (WeasyPrint).
- **Contractor-editable PDF terms** (`terms_en` / `terms_fr`, with a sane default boilerplate).
- **Logo upload** (stored on a Railway volume) shown on PDFs.
- Customer + quote CRUD; quote status lifecycle.
- Dashboard: open quotes, win rate, avg margin, **AI-usage/cost view**, and **per-assembly usage + edit-rate metrics**.
- **Code Reference page**: per-province regulator, permit model, current/pending code edition, transition windows (bilingual).
- Stateless **estimate preview** endpoint (compute without persisting).

## 5. What the app is NOT (still explicitly cut)

Do not build these: voice/speech, photo/OCR, QuickBooks/accounting, e-signature, GPS/job-tracking, team accounts/roles/multi-user orgs, scheduling/dispatch, customer-paid Stripe links, AI upsell, non-electrical trades, dark mode, native apps, offline/PWA, Redis/Celery/workers, multiple LLM providers. **Stripe billing is not yet built** (deferred until paid users exist). **Customer emailing is not built** — `send` only records status; SMTP is used solely for password-reset email.

## 6. Tech Stack (as in the repo)

### Frontend (`apps/web`)
- React 18 + Vite 6 + TypeScript (strict)
- TailwindCSS v3
- Zustand (small client store), TanStack Query (server state)
- React Hook Form + Zod
- Framer Motion (sparingly), Recharts (dashboard)
- react-i18next (`en` / `fr`)
- `openapi-typescript` generates `src/api/schema.ts` from the API's OpenAPI
- In-browser PDF preview via an `<iframe>` to the server-rendered PDF (no `react-pdf` dependency in practice)

### Backend (`apps/api`, package `quoteforge_api`)
- Python 3.12, FastAPI
- SQLAlchemy 2.0 async + asyncpg; Alembic (async env)
- Pydantic v2 + pydantic-settings
- `anthropic` SDK; `weasyprint` + `jinja2` for PDFs
- `argon2-cffi` (Argon2id), `python-jose` JWT, `httpx`, `pyyaml`, `python-multipart`
- `sentry-sdk` (optional)
- Dev: `pytest` + `pytest-asyncio`, `ruff`, `aiosqlite` (tests run on SQLite)

### AI
- `claude-sonnet-4-5` (configurable via `ANTHROPIC_MODEL`).
- Tool use for all structured outputs; prompt caching on the assembly-index block.
- No other providers; not abstracted.

### Infra
- Single Railway service. **Multi-stage Dockerfile**: `node:22-slim` builds the web app → copied into the `python:3.12-slim` image at `apps/api/static/`; data copied to `data/`.
- One Postgres. All secrets via env vars.
- `CMD` runs uvicorn; **migrations run in-app at startup for deployed envs** (`is_deployed`), guarded by a Postgres advisory lock held *inside* the migration transaction.
- Health check: `GET /api/healthz` (DB connectivity + startup state; never 500s on a bad DB URL).
- Structured JSON logs to stdout.

### Repo layout (actual)
```
/QuoteForge
├── apps/
│   ├── api/quoteforge_api/  main.py config.py db.py observability.py db_migrate.py
│   │                        code_editions.py pricebook.py money.py provinces.py
│   │     ├── auth/          security, dependencies, ratelimit
│   │     ├── routes/        auth me customers quotes estimate dashboard meta
│   │     ├── models/        user customer quote(+lineitem,flag,llmsession,refreshtoken) enums
│   │     ├── schemas/       quote estimate (+ auth/customer/user schemas)
│   │     ├── services/      estimating/ audit/ pdf/ tax/ llm/ logos.py email.py quote_service.py
│   │     ├── assemblies/    loader.py schema.py  (loads /data YAML)
│   │     └── alembic/       versions/ env.py
│   │     └── tests/         pytest (SQLite)
│   └── web/  src/{pages,components,api,stores,lib,i18n}  e2e/ (Playwright)
├── data/
│   ├── assemblies/          49 × *.yaml  (all status: draft)
│   ├── pricebook/materials.json  (68 SKUs)
│   └── code_editions.yaml   per-province code matrix (bilingual)
├── docs/    BUILD_PROMPT.md (frozen v1) · APP_SPEC.md (this file)
├── Dockerfile · railway.json · docker-compose.yml · README.md · openapi.json
```

## 7. Data Model (current tables)

Seven tables. Money = `Numeric(12,2)`, hours = `Numeric(8,2)`, pct = `Numeric(6,2)`.

- **users** — `id, email, password_hash, full_name, business_name, province, language`; licences `esa_license_number, rbq_license_number, cmeq_membership_number`; rates `blended_labor_rate_cad, apprentice_labor_rate_cad, labor_cost_rate_cad` (loaded cost used **only** for margin; 0 ⇒ fall back to billed rate), markups `default_material_markup_pct (35), default_labor_markup_pct (0)`, `minimum_callout_hours (1), minimum_margin_pct (20)`; business contact `business_email, business_phone, business_city, business_postal_code`; branding `logo_url, primary_color_hex`; **`terms_en, terms_fr`**; timestamps.
- **customers** — per-user; name, company, email, phone, address, city, province, postal_code, notes.
- **quotes** — `quote_number` (`Q-YYYY-NNNN`, per-contractor sequential), `status` (draft|sent|approved|declined|expired); job context; **locked** `province` + `code_edition` + `permit_expected_date`; engine-written subtotals (materials/labour/permits/other), `tax_gst_cad`, `tax_pst_qst_hst_cad`, `total_cad`, `gross_margin_pct`; `customer_facing_scope_en/fr`, `internal_notes`, `audit_passed`, `audit_overrides` (JSON); `valid_until`, `customer_language`; timestamps + `sent_at`/`approved_at`. Unique `(user_id, quote_number)`.
- **quote_line_items** — `line_number, source (assembly|custom|permit), assembly_id?, description_en/fr, quantity, parameters (JSON), materials_cost_cad, labor_hours, labor_cost_cad, line_total_cad, code_refs (JSON), is_optional`. Generated lines (e.g. minimum call-out) carry `assembly_id=NULL` and a `_generated` marker in `parameters`. `is_optional` lines are priced individually but excluded from the project subtotals/tax/total/margin (§24.4); `QuoteOut.optional_subtotal_cad` (computed) exposes their pre-tax sum.
- **estimate_audit_flags** — `severity (info|warn|critical), code, message_en/fr, suggested_action, overridden, overridden_at`.
- **llm_sessions** — `messages, tool_calls (JSON), input_tokens, output_tokens, cost_cad, created_at` (debug + cost surface, dashboard source).
- **refresh_tokens** — hashed, rotated on use.

Migrations (Alembic): initial schema → `labor_cost_rate_cad` → business contact fields → `terms_en/terms_fr`.

## 8. The Assembly System

YAML schema unchanged from v1 (`schema_version, id, category, trade, work_type, names{en,fr}, description{en,fr}, parameters{type:number|enum|boolean, default, values, sensitivity, prompt_en/fr, labor_multipliers}, materials[{sku, qty|qty_formula, waste}], labor{base_hours, phase, apprentice_compatible, minimum_callout_applies}, provincial_variants{<PROV>:{code_edition(s), code_refs, materials_override, labor_override, permit_handling, customer_language_default, transition_period_until}}, audit_flags[{condition, severity, message_en/fr}], last_reviewed, reviewed_by, status`).

- `/api/assemblies` returns the full index (incl. drafts, flagged) with each parameter's `type/default/values/sensitivity`.
- The **LLM index** exposes reviewed-only by default; `LLM_INCLUDE_DRAFT_ASSEMBLIES=true` (dev/test) exposes drafts so the flow is exercisable pre-review.
- **Current reality:** 49 files present, **all `draft`** → a licensed electrician must review prices/labour/code_refs per province before launch. Numeric params may be sent as strings; the engine coerces via Decimal.

## 9. Estimating Engine (`services/estimating/`)

Pure Python, deterministic, fully unit-tested. Pipeline: material price book → material expander (`qty_formula` via a safe AST evaluator, no `eval`) → labour calculator (base_hours × enum multipliers × qty, province `labor_override`, minimum call-out as a generated line) → permit lookup → tax → markup → margin. Public surface includes `compute_estimate(...)`, plus helpers (`effective_materials`, `unit_labor_hours`) reused by the audit. Reference-estimate fixtures guard against drift.

## 10. Audit Engine (`services/audit/`)

Pure Python. Rule families: missing items (permit-when-service-change, AFCI for new dwelling circuits, travel for long jobs, HQ coordination for QC service changes), margin (below minimum, labour-ratio band), per-assembly labour plausibility band, stale pricing (>90 days), scope-risk language, provincial-specific (QC customer-language, QC transition warning, ON ESA notification), and **real-world estimating protection (§24.3)**: utility-locate-required, excavation-conditions-assumed, concealed-access-assumed, material-price-volatility, service-capacity-verify, customer-supplied-equipment, permit/inspection-timeline, weather-delay. Each rule returns `None`/`[]` or a `Flag`. Critical flags set `pdf_blocked`; the §24.3 rules are info/warn only (never block) and consider the committed (non-optional) scope. Override is logged.

## 11. Provincial Tax Rules (`services/tax/`)

Table-driven with an effective date. ON HST 13%; QC GST 5% + QST 9.975% (QST on pre-GST base, not stacked); BC GST 5% + PST 7% materials-only; AB GST 5%; SK GST 5% + PST 6% materials-only; MB GST 5% + RST 7% materials-only; NS/NB/NL/PE HST 15%. Single `compute_taxes(...) → TaxBreakdown`, fixture-tested.

## 12. Code Matrix (NEW vs v1) — `data/code_editions.yaml` + `code_editions.py`

Single source of truth for per-province regulatory context, surfaced at `GET /api/code-editions` and the Code Reference page. Each of the ten provinces carries **bilingual** `regulator {en,fr}` and `permit_model {en,fr}`, `current_edition`/`pending_edition` (with `label`), and optional `transition {start,end}` (QC: 2026-03-26 → 2026-09-26). API: `edition_in_force(province, on_date)`, `in_transition`, `customer_language`. Province keys are quoted in YAML (`"ON":`) to dodge YAML 1.1 boolean coercion. Matrix `status: draft` until reviewed.

## 13. LLM Orchestration (`services/llm/`)

`claude-sonnet-4-5`, prompt caching on the assembly index. Tools: `get_assembly_detail`, `compute_estimate` (the only path to numbers), `lookup_permit_fees`, `audit_estimate`, `ask_contractor` (pauses; **max 4** questions, only high-sensitivity params that move the estimate >10%). System prompt carries contractor context, today's date, customer language, the compact assembly index, and the hard rules (no math, no invented IDs/code sections, defaults-as-assumptions, QC transition question). **Continuous conversation:** a pending `ask_contractor` is answered as a tool result; any other message continues the same session to refine the quote. Safety cap `LLM_MAX_TOOL_TURNS=12`. Every session is persisted to `llm_sessions` with tokens + CAD cost.

## 14. API Routes (actual)

```
auth      POST /api/auth/register|login|refresh
          POST /api/auth/password-reset/request|confirm        (rate-limited)
me        GET/PATCH /api/me        POST /api/me/logo
customers GET/POST /api/customers  GET/PATCH/DELETE /api/customers/{id}
quotes    GET/POST /api/quotes     GET/PATCH/DELETE /api/quotes/{id}
          POST /api/quotes/{id}/generate|answer-question|recompute|audit
          POST /api/quotes/{id}/override-flag|finalize|send|mark-status
          GET  /api/quotes/{id}/pdf?variant=customer|internal
estimate  POST /api/estimate/preview                            (stateless compute)
dashboard GET  /api/dashboard/stats       GET /api/dashboard/assemblies
meta      GET  /api/healthz  /api/assemblies  /api/code-editions  /api/logos/{user_id}
```
JSON everywhere, UUID paths, Pydantic v2 schemas, OpenAPI → frontend types. Every customer/quote query is filtered by `user_id` (repository-layer tenancy, never frontend).

## 15. PDF Generation (`services/pdf/`)

WeasyPrint + Jinja. Customer template (EN/FR, localized dates/currency `fr-CA`) and an **internal** variant (`?variant=internal`) with full materials/labour breakdown, code refs, assumptions, and audit history. Header carries logo + business contact + ESA (ON) / RBQ+CMEQ (QC) licences. Includes line items grouped by category (note: Jinja context key is `group.lines`, not `group.items`), tax lines with rates, totals, **contractor terms** (`_terms(user, lang)` with default fallback), bilingual `_code_block`, and a signature block. Customer PDF is blocked while a critical flag is unresolved.

## 16. Frontend Pages (actual routes)

`/login /register /forgot-password /reset-password`; protected: `/` → `/dashboard`, `/dashboard`, `/customers` `/customers/new` `/customers/:id`, `/quotes` `/quotes/new` `/quotes/:id` `/quotes/:id/pdf-preview`, **`/code-reference`**, `/settings` (+ `/settings/labor-rates`, `/settings/markup`).

**Quote Builder** = three columns desktop / tabs mobile (**Chat | Estimate | Preview**):
- **Chat** — continuous transcript with a persistent input; answers questions or refines.
- **Estimate** — live engine output; edit quantity, remove lines, add assemblies, and an **Options** editor per assembly line to change declared **parameters** (enum dropdown / boolean checkbox / numeric); Recompute persists + re-prices. Audit flags with override.
- **Preview** — customer-facing scope, province · code edition, PDF (customer/internal), finalize/send/status.

Mobile: ≥44px targets, correct `inputmode`, loading states on every async action.

## 17. Auth & Security

Argon2id (t=3, m=64MB, p=4). JWT access 15 min; refresh 30 days, rotated, stored hashed. Same-origin CORS. Rate limits on `/auth/*` and `/quotes/*/generate` — **`LLM_GENERATES_PER_HOUR=40`** (raised from the v1 spec's 10 so iterative chat refinement isn't throttled). Password reset = signed 1-hour token via SMTP. Pydantic validation at the boundary; SQLAlchemy parameterization; per-user data isolation enforced server-side.

## 18. Internationalization

react-i18next `en.json`/`fr.json`, every UI string keyed. UI language follows the user; customer PDF follows per-quote `customer_language`. Assembly/code text shown in contractor's language in the editor, customer's on the PDF. `Intl` for numbers/dates; CAD only. **Stored French is machine-drafted pending professional + Quebec-electrician sign-off.**

## 19. Deployment & Observability

Railway single service (multi-stage Docker, §6). Env vars: `DATABASE_URL, JWT_SECRET, ANTHROPIC_API_KEY, ANTHROPIC_MODEL?, SMTP_*, LOG_LEVEL, LOG_FORMAT, ENVIRONMENT, SENTRY_DSN?, LLM_GENERATES_PER_HOUR?, LLM_INCLUDE_DRAFT_ASSEMBLIES?`. `DATABASE_URL` is normalized (`postgres://`→`postgresql+asyncpg://`, whitespace stripped, `sslmode`→connect_args). Migrations auto-run on startup in deployed envs under an advisory lock held inside the transaction (non-fatal on failure → degraded `/healthz`). Observability: structured JSON logs; Sentry when DSN set; dashboard exposes per-user LLM cost/tokens/sessions and **per-assembly usage + edit-rate** (high edit rate = defaults likely off → prioritize for review).

## 20. Testing

`pytest` on SQLite (93 tests green): engine, audit, tax, formula, assemblies, code editions, config, LLM, and end-to-end app flow (auth, isolation, quote lifecycle, dashboard stats + assembly metrics, PDF gating, logo, QC French). Playwright e2e specs exist (`golden-path`, `dashboard`) but **require Chromium**, which can't be installed in the build sandbox — run them locally/CI with `npx playwright install chromium && npm run e2e`. `ruff` lint clean.

## 21. Definition of Done — NOT YET MET

Pre-launch, human (not code) work remaining:
1. **Electrician review** of all 49 assemblies' prices, labour hours, and `code_refs` per province; expand the price book toward ~200 real SKUs; flip reviewed assemblies to `status: reviewed`.
2. **Professional French** for stored content + a **Quebec electrician** sign-off on terminology and the FR PDF.
3. A **live in-browser / E2E pass** (golden path on a real phone over LTE) in CI.
4. Verify the 10 reference estimates against an electrician's hand calcs (±$5).

## 22. Resolved decisions (were §23 open questions)

- **Quote numbering:** per-contractor sequential, `Q-YYYY-NNNN`.
- **Logo storage:** Railway volume (`LOGO_STORAGE_DIR`), served via `/api/logos/{user_id}`.
- **Customer emailing:** not in scope — `send` records status only; SMTP is password-reset only.
- **Multi-location contractors:** no (single-tenant per contractor).
- **Subscription pricing / Stripe:** still deferred (no billing built).
- **Quote expiry default:** `valid_until` field exists; set a default policy before launch.

## 23. Things still not to add

YAML-in-git assemblies (no admin UI), Claude-only (no provider abstraction), no queue (FastAPI background tasks), no feature-flag system, no Spanish, pytest only. CI = GitHub Actions lint+test on PR, deploy on merge. If a feature feels easy to add but isn't in §4, it belongs in §5.

## 24. Contractor Realism & Proposal Quality Layer

> **Partially implemented.** This is the quality bar QuoteForge proposals must hit. Done so far: the scope-prose tone/terminology/trust block in the LLM system prompt (24.1/24.2/24.4), clean multi-paragraph PDF scope (24.5), the optional add-on split end-to-end (24.4), and the real-world risk-assumption audit rules (24.3). Still **new work**: a hard terminology lint at finalize (24.2), assembly confidence scoring (24.6), and the engineering sanity checks (24.7) — several of which depend on electrician-reviewed data. Build it in the §3 spirit: the model improves *language and presentation*, never the numbers, and never invents code/technical facts.

**Goal.** Proposals must feel indistinguishable from high-end professional estimating software used by experienced Canadian electrical contractors — optimizing for homeowner trust, contractor protection, technical credibility, fewer disputes, higher close rates, and field practicality. Applies to AI scope text, PDF layout, estimate explanations, exclusions, assumptions, recommendation language, terminology, risk disclosure, and presentation.

### 24.1 Proposal generation rules (AI scope prose)
Generated prose must be concise, experienced, and field-practical — sounding like a premium residential electrical contractor / seasoned estimator / practical PM / homeowner-friendly professional. **Avoid:** robotic AI phrasing, generic sales language, excessive jargon, vague scope wording. **Never sound like:** marketing copy, startup software, AI fluff, legal overkill, or an engineering textbook. (Enforced in the LLM system prompt + a post-generation style pass; numbers and code refs stay engine/data-sourced per §3.)

### 24.2 Technical terminology enforcement
The system must distinguish, and use correctly: utility service · feeder · subfeed · distribution panel · disconnect · subpanel · branch circuits. A detached structure fed from the house is **never** a "new utility service" — prefer "garage feeder" / "garage electrical feed" / "garage distribution panel." The AI must detect terminology misuse and **self-correct before PDF generation** (terminology lint as a finalize-time gate).

### 24.3 Real-world estimating protection
Every estimate should automatically consider, and the audit engine (§10) should **warn or surface an assumption** when missing: trenching difficulty · rock-excavation risk · utility-locate conflicts · concealed-space access · material price volatility · permit delays · weather delays · customer-supplied equipment compatibility · service-capacity verification · code-transition periods · inspection-scheduling delays.
**Implemented** as eight deterministic info/warn audit rules that key off the committed (non-optional) assemblies + scope text and suppress themselves when the scope already addresses the risk: `UTILITY_LOCATE_REQUIRED`, `EXCAVATION_CONDITIONS_ASSUMED` (covers trenching difficulty + rock), `CONCEALED_ACCESS_ASSUMED`, `MATERIAL_PRICE_VOLATILITY`, `SERVICE_CAPACITY_VERIFY` (load added without a service upgrade), `CUSTOMER_SUPPLIED_EQUIPMENT`, `PERMIT_INSPECTION_TIMELINE`, `WEATHER_DELAY_RISK`. Code-transition periods are already handled by `CODE_EDITION_TRANSITION` (§12). These never block the PDF and appear to the contractor (builder + internal PDF), not on the customer proposal.

### 24.4 Customer-trust optimization
Customer PDFs should explain recommendations, justify upgrades without pressure, reduce sticker shock, **separate required vs optional work**, and explain future-proofing value. Preferred framing: "room for future expansion," "avoids future upgrade costs," "supports future EV charging," "improves long-term flexibility." Avoid aggressive upselling.
**Implemented:** line items carry `is_optional`; the AI (via the `compute_estimate` tool) and the contractor (via a per-line toggle in the builder) can mark recommended work optional. Optional add-ons are priced individually and **excluded** from the project total and margin; the customer PDF shows them in a separate "Optional add-ons" section with a tax-inclusive "if added" total, and the builder shows an "Optional add-ons (not in total)" line. Future-proofing prose framing is enforced via the §24.1 system-prompt block.

### 24.5 PDF presentation quality
Customer proposals should resemble Jobber / Joist / Housecall Pro — clean spacing, readable tables, work grouped by category, concise descriptions, minimal clutter, visually obvious totals, strong hierarchy. **Never** generate giant text blocks, duplicated sections, repetitive scope wording, or material dumps in the customer PDF. Internal PDFs may carry full technical detail; customer PDFs prioritize clarity (extends §15's customer/internal split).

### 24.6 Assembly confidence system
Assemblies should grow (beyond today's `status: draft|reviewed`): reviewed confidence score · electrician review count · province-review completeness · last field-validation date · edit-frequency metrics (the §19 edit-rate feeds this) · actual-vs-estimated variance tracking. High customer-risk assemblies surface warnings **internally**.

### 24.7 Estimate sanity checks (finalize-time)
Before finalizing, verify: markup logic · margin thresholds · conductor sizing consistency · breaker compatibility · receptacle/circuit compatibility · service terminology · provincial tax handling · code-edition references. If patterns look unrealistic, **surface a warning to the contractor — never silently continue.** Implement as new deterministic audit rules (§10), not as LLM judgment.

### 24.8 Competitive positioning
QuoteForge should feel smarter than generic quoting apps, safer than AI-only estimators, more contractor-aware than consumer software, more trustworthy than chat-based AI quoting tools. **The moat is** deterministic estimating · contractor realism · province-aware code logic · audit protection · assembly quality · proposal professionalism — **not chatbot novelty.**

-----

## End of Live Spec

Working rules for the agent: ask before deviating from any §3 principle; keep `docs/BUILD_PROMPT.md` frozen as history and update **this** file when behaviour changes; engine before LLM, test engine before UI, audit before PDF; never let the model produce a number; never ship a `draft` assembly's pricing as if reviewed.
