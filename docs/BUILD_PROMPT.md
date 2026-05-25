# QuoteForge — Build Prompt

> **Use this prompt with Claude Code, Cursor, or any agentic coding tool.** It is intentionally opinionated and scope-limited. Do not expand scope without explicit instruction.

-----

## 1. Project Identity

**Name:** QuoteForge
**Tagline:** AI-powered estimating for Canadian electrical contractors.
**Audience for v1:** Licensed electrical contractors in Canada (Ontario and Quebec at launch; architecture supports all provinces).
**Built by:** Solo founder. Optimize for one person maintaining the entire stack.

## 2. The One-Sentence Pitch

A contractor describes a job in plain language (typed); QuoteForge produces an accurate, code-aware estimate and a customer-ready proposal in under five minutes, and warns the contractor before they underbid.

## 3. Non-Negotiable Architectural Principles

These are not suggestions. Violating them means rewriting later.

1. **The LLM never does math.** It interprets language and maps work to a curated assembly library. All numeric calculations happen in deterministic Python. If you find the model producing a price, that’s a bug.
1. **Assemblies are the product.** The pricing/labor library is the moat. The UI and AI are wrappers around it. Build the library schema first, with real values reviewed by an electrician, before writing any frontend code.
1. **Province is a first-class dimension.** Every assembly, every tax calculation, every permit lookup, every PDF template knows the province. There is no “default Canada” mode.
1. **Code edition is tracked per quote.** Quebec is mid-transition (CCÉ 2015 → CCÉ 2021 with QC amendments, effective March 26, 2026, with a six-month transition window ending September 26, 2026). The quote records which edition applied at quote time.
1. **Profit protection is a headline feature, not a footnote.** Every estimate runs through an audit pass before the PDF can be generated. Critical flags block PDF rendering until the contractor explicitly overrides.
1. **No hallucinated code citations.** Code section references on customer documents come only from verified `code_refs` fields in the assembly library. If a citation isn’t in the data, it isn’t in the document.
1. **French is professionally translated, never LLM-translated for stored content.** LLM-generated French is allowed only for the customer-facing prose written at quote time, never for material names, code references, or technical terms.
1. **No offline mode in v1.** Mobile-responsive web app, fully online. Native app and offline-first are deferred.

## 4. What v1 IS

- Web app, mobile-responsive (works well on a phone in a truck cab on LTE).
- One trade: electrical.
- Two provinces at launch: Ontario and Quebec. Schema supports all ten.
- ~50 assemblies covering the most common residential/light-commercial electrical jobs.
- AI quote generation from typed text input.
- Deterministic estimating engine (materials, labor, tax, markup).
- Profit-protection audit pass.
- Bilingual (English / French) customer-facing PDFs.
- Customer + quote CRUD.
- Simple dashboard: open quotes, win rate, average margin.
- Stripe-based subscription billing (deferred until paid users exist).
- Single-tenant per contractor (no team accounts in v1).

## 5. What v1 IS NOT (Explicitly Cut)

Do not build any of these. They are listed only so the coding agent does not “helpfully” add them:

- Voice input / speech-to-text.
- Photo upload and analysis.
- OCR.
- QuickBooks / accounting integration.
- E-signature.
- GPS / job tracking.
- Team accounts, roles, multi-user organizations.
- Scheduling / dispatch.
- Stripe payment links for customer-paid quotes.
- AI upsell suggestions.
- Industry templates beyond electrical.
- Dark mode (light mode only; ship faster).
- Native mobile apps.
- Offline mode / PWA install.
- Redis, Celery, background workers (use FastAPI BackgroundTasks if anything async is needed).
- Multiple LLM providers (Claude only; do not abstract).

If a feature in this list would be “easy to add,” do not add it. Validation comes first.

## 6. Tech Stack

### Frontend

- React 18 + Vite + TypeScript
- TailwindCSS
- Zustand for client state (one store, kept small)
- React Hook Form + Zod for forms
- TanStack Query for server state
- Framer Motion only where it adds clarity (sparingly)
- Recharts for dashboard
- `react-pdf` for in-browser PDF preview (rendering of final PDF happens server-side)

### Backend

- Python 3.12, FastAPI
- PostgreSQL 16
- SQLAlchemy 2.0 (async)
- Alembic migrations
- Pydantic v2
- `anthropic` Python SDK for Claude
- `weasyprint` for PDF generation (HTML/CSS → PDF; reliable, headless-friendly)
- `argon2-cffi` for password hashing
- `python-jose` for JWT
- `httpx` for outbound calls

### AI

- Anthropic Claude (`claude-sonnet-4-5` for the main estimating loop)
- Tool use for all structured outputs
- Prompt caching on the assembly index block
- No OpenAI fallback in v1

### Infra

- Single deployment on Railway
- One web service (FastAPI serving the API + serving the built frontend as static files)
- One Postgres
- Environment variables for all secrets
- Health check at `/healthz`
- Structured logging (JSON) to stdout

### Repo Layout

```
/quoteforge
├── apps
│   ├── api/                  # FastAPI
│   │   ├── quoteforge_api/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   ├── auth/
│   │   │   ├── routes/
│   │   │   ├── models/       # SQLAlchemy
│   │   │   ├── schemas/      # Pydantic
│   │   │   ├── services/
│   │   │   │   ├── estimating/      # The engine. Pure Python.
│   │   │   │   ├── audit/           # Profit protection. Pure Python.
│   │   │   │   ├── pdf/             # WeasyPrint
│   │   │   │   ├── tax/             # Provincial tax rules
│   │   │   │   └── llm/             # Claude orchestration
│   │   │   └── assemblies/          # YAML files, loaded at startup
│   │   ├── alembic/
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── web/                  # Vite + React
│       ├── src/
│       │   ├── pages/
│       │   ├── components/
│       │   ├── api/          # Generated from OpenAPI schema
│       │   ├── stores/
│       │   ├── hooks/
│       │   └── i18n/         # en + fr translation files
│       ├── public/
│       ├── index.html
│       └── package.json
├── data
│   └── assemblies/           # Source YAML, version-controlled
├── docs
├── docker-compose.yml        # Local dev only
├── Dockerfile                # Production
├── railway.json
└── README.md
```

The frontend builds to `apps/web/dist` and is served by FastAPI as static files at root. The API lives at `/api/*`. One service, one URL, simpler deploy.

## 7. Data Model

Core tables only. Migrations via Alembic.

```python
# Pseudocode for the schema — use SQLAlchemy 2.0 declarative

class User:
    id: UUID
    email: str (unique)
    password_hash: str
    full_name: str
    business_name: str
    province: Enum[ON, QC, BC, AB, MB, SK, NS, NB, NL, PE]
    language: Enum[en, fr]
    
    # Licensing (province-dependent fields, all optional)
    esa_license_number: str | None      # Ontario
    rbq_license_number: str | None       # Quebec
    cmeq_membership_number: str | None   # Quebec
    
    # Business defaults
    blended_labor_rate_cad: Decimal      # $/hr including burden
    apprentice_labor_rate_cad: Decimal
    default_material_markup_pct: Decimal # e.g. 35.0
    default_labor_markup_pct: Decimal    # often 0 (rate already loaded)
    minimum_callout_hours: Decimal       # e.g. 1.0
    minimum_margin_pct: Decimal          # audit trigger; e.g. 20.0
    
    # Branding
    logo_url: str | None
    primary_color_hex: str | None
    
    created_at: datetime
    updated_at: datetime

class Customer:
    id: UUID
    user_id: UUID
    name: str
    company: str | None
    email: str | None
    phone: str | None
    address_line1: str
    address_line2: str | None
    city: str
    province: Enum[...]
    postal_code: str
    notes: str | None
    created_at: datetime

class Quote:
    id: UUID
    user_id: UUID
    customer_id: UUID
    quote_number: str         # human-readable, e.g. "Q-2026-0142"
    status: Enum[draft, sent, approved, declined, expired]
    
    # Job context
    job_title: str
    job_description: str      # original contractor input
    job_site_address: str | None  # may differ from customer address
    
    # Code/regulatory context — locked at quote time
    province: Enum[...]
    code_edition: str         # e.g. "OESC 2024 (28th)"
    permit_expected_date: date | None
    
    # Computed totals — written by the estimating engine, never edited by LLM
    subtotal_materials_cad: Decimal
    subtotal_labor_cad: Decimal
    subtotal_permits_cad: Decimal
    subtotal_other_cad: Decimal
    tax_gst_cad: Decimal
    tax_pst_qst_hst_cad: Decimal
    total_cad: Decimal
    gross_margin_pct: Decimal
    
    # AI metadata
    customer_facing_scope_en: str | None
    customer_facing_scope_fr: str | None
    internal_notes: str       # assumptions, code refs, contractor-only
    audit_passed: bool
    audit_overrides: JSON     # which critical flags the contractor dismissed
    
    valid_until: date
    customer_language: Enum[en, fr]
    
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    approved_at: datetime | None

class QuoteLineItem:
    id: UUID
    quote_id: UUID
    line_number: int
    
    source: Enum[assembly, custom, permit]
    assembly_id: str | None       # references YAML library
    description_en: str
    description_fr: str
    
    quantity: Decimal
    parameters: JSON               # the resolved parameters (run_length_ft, etc.)
    
    materials_cost_cad: Decimal
    labor_hours: Decimal
    labor_cost_cad: Decimal
    line_total_cad: Decimal
    
    code_refs: JSON                # array of {section, note}

class EstimateAuditFlag:
    id: UUID
    quote_id: UUID
    severity: Enum[info, warn, critical]
    code: str                      # machine-readable, e.g. "MARGIN_BELOW_MIN"
    message_en: str
    message_fr: str
    suggested_action: str
    overridden: bool
    overridden_at: datetime | None

class LLMSession:
    id: UUID
    quote_id: UUID
    messages: JSON                 # full Claude conversation
    tool_calls: JSON               # for debugging & later fine-tuning data
    input_tokens: int
    output_tokens: int
    cost_cad: Decimal
    created_at: datetime
```

The assembly library is **not in the database** in v1. It lives as version-controlled YAML files under `/data/assemblies/`, loaded into memory at startup. This is intentional: assemblies change rarely, need code review on every change, and are easier to manage in git than in an admin UI you don’t have time to build. Move to DB when you have a second person editing them.

## 8. The Assembly System

Each assembly is a YAML file. Schema:

```yaml
schema_version: "1.0"
id: <unique_snake_case_id>
category: <devices|panels|service|lighting|circuits|special>
trade: electrical
work_type: [service, renovation, new_construction]

names:
  en: "English name"
  fr: "Nom français"

description:
  en: "What this assembly covers, in one sentence."
  fr: "Ce que couvre cet ensemble, en une phrase."

parameters:
  <param_name>:
    type: number | enum | boolean
    default: <value>
    values: [enum_value_1, enum_value_2]   # for enums only
    sensitivity: low | medium | high
    prompt_en: "Question shown to contractor when this needs to be asked."
    prompt_fr: "..."
    labor_multipliers:                      # for enums
      <value>: <multiplier>

materials:
  - sku: <material_sku>
    qty: <number> | qty_formula: "expression using parameters"
    waste: <decimal 0-1>

labor:
  base_hours: <decimal>
  phase: rough_in | trim | service | special
  apprentice_compatible: <bool>
  minimum_callout_applies: <bool>

provincial_variants:
  ON:
    code_edition: "OESC 2024 (28th)"
    code_refs:
      - section: "Rule 26-712"
        note: "Brief plain-language note for internal use"
    materials_override: [...]      # additions or replacements
    labor_override: { base_hours: ... }
    permit_handling: "ESA notification required"
  QC:
    code_edition_current: "Chapitre V (CCÉ 2015 + modifications QC)"
    code_edition_pending: "Chapitre V 2026 (CCÉ 2021 + modifications QC)"
    transition_period_until: "2026-09-26"
    code_refs: [...]
    labor_override: { ... }
    customer_language_default: fr
  BC: { ... }
  AB: { ... }
  # other provinces as needed

audit_flags:
  - condition: "<expression>"     # evaluated server-side
    severity: info | warn | critical
    message_en: "..."
    message_fr: "..."

last_reviewed: "YYYY-MM-DD"
reviewed_by: <reviewer_id>
```

**Required assemblies for v1** (the minimum viable library — build these first, with real values reviewed by an electrician):

```
SERVICE & PANELS
- service_upgrade_100a_overhead
- service_upgrade_200a_overhead
- service_upgrade_200a_underground
- subpanel_60a
- subpanel_100a
- panel_relocation_existing

DEVICES & CIRCUITS
- recep_duplex_15a_residential
- recep_duplex_20a_residential
- recep_gfci_residential
- recep_240v_30a_dryer
- recep_240v_50a_range
- switch_single_pole
- switch_3way
- switch_dimmer
- circuit_new_15a_residential
- circuit_new_20a_kitchen
- circuit_new_240v_30a
- circuit_new_240v_50a
- afci_breaker_retrofit

LIGHTING
- pot_light_residential_remodel
- pot_light_residential_new
- light_fixture_replace
- light_fixture_install_new
- light_fixture_exterior
- light_fixture_chandelier_tall

EV & APPLIANCES
- ev_charger_l2_attached_garage
- ev_charger_l2_detached_garage
- ev_charger_l2_outdoor
- hot_tub_circuit_240v
- range_hood_circuit
- dishwasher_circuit
- microwave_circuit

SAFETY & SPECIAL
- smoke_alarm_hardwired_install
- co_alarm_hardwired_install
- bathroom_fan_install
- bathroom_fan_replace
- doorbell_wired
- generator_inlet_30a
- generator_inlet_50a

TROUBLESHOOTING & REPAIR
- service_call_diagnostic
- circuit_troubleshoot_dead
- gfci_replace
- breaker_replace
- aluminum_wiring_pigtail_per_device

EXTERIOR & ROUGH-IN
- outdoor_outlet_install
- yard_light_install
- conduit_run_emt_per_ft
- conduit_run_pvc_buried_per_ft
- trench_per_ft

TOTAL: ~50 assemblies
```

Each assembly must be reviewed by a working electrician in the target province before shipping. Mark unreviewed assemblies as `status: draft` and exclude them from the LLM’s index.

## 9. The Estimating Engine (Build This First)

`apps/api/quoteforge_api/services/estimating/` — pure Python, no LLM dependency, fully unit-tested.

```python
# Public interface
def compute_estimate(
    contractor: User,
    province: Province,
    municipality: str | None,
    code_edition_at_permit_date: date,
    assemblies: list[AssemblyRequest],
    additional_line_items: list[CustomLineItem] = None,
) -> EstimateResult:
    """
    Computes a complete estimate. Pure function, deterministic.
    
    Returns:
        EstimateResult with:
          - line_items: list of computed lines
          - subtotals: materials, labor, permits, other
          - taxes: GST and PST/QST/HST per provincial rules
          - total
          - gross_margin_pct
          - assumptions: list of default values used
    """
```

**Build order inside the engine:**

1. **Material price book.** Start with a flat JSON file of SKUs with `cost`, `last_updated`, `unit`, `supplier`. ~200 SKUs covers v1. Source initial prices from a real supplier catalogue (Gescan, Westburne, Nedco) with your electrician contact’s help. Mark anything older than 90 days as stale.
1. **Material expander.** Given an assembly + parameters, produce a flat list of `(sku, qty_after_waste)`.
1. **Labor calculator.** Apply `labor.base_hours × parameter multipliers × quantity`. Apply minimum callout. Split journeyman vs apprentice hours if applicable.
1. **Permit lookup.** Static lookup table by `(province, work_category)`. Hardcode current ESA/RBQ/TSBC fees; flag for review every 6 months.
1. **Tax calculator.** Provincial rules (see section 11).
1. **Markup applier.** Contractor’s defaults, overridable per quote.
1. **Margin computer.** Output gross margin %.

**Test it ruthlessly.** Hand-construct 10 reference estimates with your electrician. Encode them as fixtures. CI fails if any reference estimate drifts.

## 10. The Audit Engine (Build This Second)

`apps/api/quoteforge_api/services/audit/` — also pure Python, no LLM.

Checks to run on every estimate:

```
RULE_CATEGORIES = {
  "missing_items": [
    # If any service-change assembly is present, permits must be present
    requires_permit_when_service_change,
    # If any new circuit is added, AFCI may be required (ON OESC 2024)
    afci_required_for_new_circuits_in_dwelling,
    # If estimated job > 4 hours, travel time should be present
    travel_time_for_long_jobs,
    # If service upgrade in QC, Hydro-Québec coordination should be present
    hq_coordination_for_qc_service_changes,
  ],
  "margin": [
    # Gross margin below contractor's minimum
    margin_below_minimum,
    # Labor below 30% of total (rare for service work, possible flag)
    labor_ratio_outside_band,
  ],
  "labor_plausibility": [
    # Per assembly, flag if labor < 70% or > 150% of base × qty
    labor_hours_outside_band_per_assembly,
  ],
  "pricing": [
    # Any material with last_updated > 90 days
    stale_material_pricing,
  ],
  "scope_risk": [
    # Original description contains hedging language
    # ("might need to", "while you're at it", "depending on what we find")
    scope_creep_language_in_description,
  ],
  "provincial_specific": [
    # Quebec: customer-facing language is French if customer address is in QC
    qc_customer_language_check,
    # Quebec transition period
    qc_code_edition_transition_warning,
    # Ontario: ESA notification language present in customer doc
    esa_notification_present_in_on_quote,
  ],
}
```

Each rule returns `None` or a `Flag(severity, code, message_en, message_fr, suggested_action)`.

**Critical flags block PDF generation.** The contractor must explicitly override (logged, with timestamp) to proceed.

## 11. Provincial Tax Rules

Implement once, table-driven. Rules as of 2026-05; build a `tax_table_effective_date` so updates are auditable:

|Province      |GST|PST/QST/HST             |Notes                                                                                                     |
|--------------|---|------------------------|----------------------------------------------------------------------------------------------------------|
|ON            |—  |HST 13%                 |HST applies to materials and labor                                                                        |
|QC            |5% |QST 9.975%              |Both apply to materials and labor; QST is calculated on the pre-GST amount (not stacked on GST since 2013)|
|BC            |5% |PST 7% on materials only|Labor generally PST-exempt; verify per job category                                                       |
|AB            |5% |—                       |No PST                                                                                                    |
|SK            |5% |PST 6% on materials only|Verify labor exemptions                                                                                   |
|MB            |5% |RST 7% on materials only|                                                                                                          |
|NS, NB, NL, PE|—  |HST 15%                 |HST applies to materials and labor                                                                        |

A single `compute_taxes(province, materials_subtotal, labor_subtotal) -> TaxBreakdown` function. Unit-tested with fixtures from real contractor invoices.

## 12. LLM Orchestration (Build This Third)

Only after the engine and audit pass tests. The LLM should never be the reason a number is wrong.

`apps/api/quoteforge_api/services/llm/estimator.py`

### Model

- `claude-sonnet-4-5` for the main estimating loop.
- Use prompt caching on the assembly index block (mark with `cache_control: {"type": "ephemeral"}`).

### Tools exposed to Claude

1. `get_assembly_detail(assembly_ids)` — returns full YAML for those assemblies.
1. `compute_estimate(...)` — wraps the engine. **The only path to numbers.**
1. `lookup_permit_fees(province, municipality, work_category, amperage)`.
1. `audit_estimate(estimate_id)` — runs the audit pass, returns flags.
1. `ask_contractor(question, why_it_matters, affects_assemblies)` — pauses the flow for input.

### System prompt structure

- Contractor context (name, province, language, license numbers).
- Today’s date.
- Customer-facing language for this quote.
- The full **assembly index** (compact form: id, en/fr names, brief description, parameter names + sensitivity). Target <30K tokens.
- Process rules (described in §13 below).

### Flow

```
User: <job description>
  ↓
Claude: identifies likely assemblies → calls get_assembly_detail
  ↓
Claude: for high-sensitivity unknown parameters → calls ask_contractor (one at a time, max 4)
  ↓
Contractor: answers
  ↓
Claude: calls lookup_permit_fees if applicable
  ↓
Claude: calls compute_estimate
  ↓
Claude: calls audit_estimate
  ↓
If critical flags: surfaces them to contractor, awaits decision
  ↓
Claude: writes customer-facing scope of work in customer_language
  ↓
End turn → backend persists the quote
```

### Hard rules (in the system prompt)

- “You do not calculate any numbers. All numeric output comes from `compute_estimate`.”
- “Never invent assembly IDs. If something doesn’t match, add it as `additional_line_items` and ask the contractor to confirm pricing.”
- “Never invent code section numbers. Only cite code references returned by `get_assembly_detail`.”
- “Maximum 4 clarifying questions per session. Only ask if the parameter is high-sensitivity AND a default would shift the estimate >10%.”
- “If the contractor says ‘just estimate it’ or similar, use defaults and list them as assumptions.”
- “Customer-facing prose: plain language, no code section numbers unless explicitly requested. Internal notes: include code refs, assumptions, audit flags.”
- “For Quebec: if `permit_expected_date` is between 2026-03-26 and 2026-09-26, ask the contractor which code edition applies. Default to the current edition otherwise.”

### Logging

Every LLM session writes to `LLMSession` with the full message history, tool calls, token counts, and cost. This is your debugging surface and, eventually, your fine-tuning dataset.

## 13. API Routes

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
POST   /api/auth/password-reset/request
POST   /api/auth/password-reset/confirm

GET    /api/me
PATCH  /api/me                            # update business defaults, branding

GET    /api/customers
POST   /api/customers
GET    /api/customers/{id}
PATCH  /api/customers/{id}
DELETE /api/customers/{id}

GET    /api/quotes                        # filterable by status
POST   /api/quotes                        # creates draft
GET    /api/quotes/{id}
PATCH  /api/quotes/{id}                   # contractor edits to line items
DELETE /api/quotes/{id}
POST   /api/quotes/{id}/generate          # starts/continues LLM session
POST   /api/quotes/{id}/answer-question   # responds to ask_contractor
POST   /api/quotes/{id}/recompute         # re-runs engine after manual edits
POST   /api/quotes/{id}/audit             # re-runs audit
POST   /api/quotes/{id}/override-flag     # dismisses a critical flag
POST   /api/quotes/{id}/finalize          # locks the quote, generates PDF
GET    /api/quotes/{id}/pdf               # streams PDF
POST   /api/quotes/{id}/send              # records sent status (does not email yet)
POST   /api/quotes/{id}/mark-status       # approved/declined/expired

GET    /api/dashboard/stats

GET    /api/healthz
```

All routes return `application/json`, use UUIDs in paths, follow REST conventions. Pydantic v2 schemas for every request/response. OpenAPI generated for frontend type generation.

## 14. PDF Generation

WeasyPrint, HTML/CSS templated. Two templates:

- `quote_en.html.jinja` — English layout.
- `quote_fr.html.jinja` — French layout. Same structure; all strings translated; date/currency formatting localized (`fr-CA`).

PDF must include:

- Contractor business header with logo, business name, address, phone, email.
- ESA license # (ON) or RBQ + CMEQ # (QC) prominently in header.
- Quote number, date, valid-until date.
- Customer block.
- Job site (if different from customer address).
- Customer-facing scope of work (from LLM, contractor-edited).
- Line items grouped by category with quantities, descriptions, and line totals. Material and labor are combined per line for customer view (contractor sees breakdown internally).
- Subtotal, tax line(s) with rate %, total.
- Terms and conditions (contractor-editable boilerplate).
- Signature block.
- Footer with QuoteForge attribution (small, removable on paid tier later).

A separate `internal_quote.html.jinja` produces the contractor-only version with full breakdown, code refs, assumptions, and audit flag history.

## 15. Frontend Pages

```
/login
/register
/forgot-password
/reset-password
/                         → redirects to /dashboard if logged in
/dashboard
/customers
/customers/new
/customers/:id
/quotes
/quotes/new               → starts the AI flow
/quotes/:id               → editor / preview
/quotes/:id/pdf-preview
/settings                 → business defaults, branding, license numbers
/settings/labor-rates
/settings/markup
```

### Quote Builder UX

Single page, three columns on desktop, stacked on mobile:

- **Left:** Conversation pane. Contractor’s input → Claude’s responses → clarifying questions → audit flags. Looks like a chat.
- **Middle:** Live estimate. Updates after each `compute_estimate` call. Editable inline (changing a quantity or removing a line triggers `recompute`).
- **Right:** Customer-facing preview. Updates after scope is written.

On mobile, these become tabs: **Chat | Estimate | Preview**.

The “send to customer” CTA is the only primary button. Everything else (edit line, override flag, regenerate scope) is secondary.

### Mobile considerations

- Hit targets ≥ 44px.
- No hover-dependent UI.
- Inputs use `inputmode` correctly (numeric for quantities, decimal for prices).
- Form validation messages above the input, not below (thumb often covers below).
- Test on a real phone on real LTE. Loading state for every async action — no silent waits.

## 16. Authentication & Security

- Argon2id password hashing (cost params: t=3, m=64MB, p=4).
- JWT access tokens, 15-min expiry. Refresh tokens, 30-day expiry, rotated on use, stored hashed.
- HTTPS only in production (Railway gives this).
- CORS: same-origin only (frontend served from same domain).
- Rate limits on `/auth/*` and `/quotes/*/generate` (cost protection): 10 generates per hour per user in v1.
- Password reset: signed token email, 1-hour expiry. Use a transactional email service via SMTP env vars; do not build an email service.
- Input validation on every endpoint via Pydantic.
- SQL injection protected by SQLAlchemy parameterization.
- PII: customer data is per-user; enforce `user_id` in every customer/quote query (RLS-style filtering in repository layer; do not rely on frontend filtering).

## 17. Internationalization

- Frontend: `react-i18next` with `en.json` and `fr.json`. Every user-facing string keyed.
- Default language follows the user’s `language` setting; customer-facing PDFs follow the per-quote `customer_language`.
- Assembly names/descriptions: always show in contractor’s language in the editor; in customer’s language on the PDF.
- Numbers: `Intl.NumberFormat` with `en-CA` or `fr-CA`. Currency: CAD only in v1.
- Dates: ISO in API, formatted via `Intl.DateTimeFormat` in UI.

## 18. Deployment

Railway:

- One service: `api`. Dockerfile builds the frontend (`npm ci && npm run build`) into `/app/static`, then builds the FastAPI app, copies frontend bundle into the image. FastAPI serves `/api/*` and falls back to `index.html` for SPA routes.
- One Postgres plugin.
- Environment variables:
  - `DATABASE_URL`
  - `JWT_SECRET` (rotate-able)
  - `ANTHROPIC_API_KEY`
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
  - `LOG_LEVEL`
  - `ENVIRONMENT` (`dev` | `staging` | `prod`)
  - `SENTRY_DSN` (optional but recommended)
- `railway.json` defines build + start commands.
- Health check: `GET /api/healthz` returns 200 with DB connectivity confirmed.
- Migrations: run automatically on startup via Alembic (with a lock to prevent multi-replica races).

## 19. Observability

- Structured JSON logs to stdout.
- Sentry for exceptions (free tier is fine).
- Track per-user metrics: quotes generated, LLM cost, audit flags raised, flags overridden, final win rate.
- Track per-assembly metrics: usage frequency, contractor edit rate (high edit rate = assembly needs review).

## 20. Order of Construction

Build in this exact order. Do not skip ahead.

**Week 1–2: Engine first, no UI.**

1. Repo scaffold, Docker, Railway hello-world deploy.
1. Postgres schema + migrations.
1. Material price book (JSON) with ~200 SKUs sourced from a real catalogue.
1. Tax engine + tests.
1. Five reference assemblies (YAML) reviewed by your electrician contact.
1. `compute_estimate()` with full tests, including the 10 hand-constructed reference estimates as fixtures.

**Week 3: Audit engine.**
7. Audit rule framework + all rules from §10.
8. Tests for each rule.

**Week 4: Auth + minimal UI.**
9. User registration, login, business settings page.
10. Customer CRUD.
11. Quote shell (no AI yet) — contractor can manually add assembly line items and see the engine produce a number.

**Week 5: LLM integration.**
12. Build the assembly index prompt.
13. Tool definitions.
14. Conversation flow with `ask_contractor` pausing.
15. End-to-end: typed job → estimate → audit → PDF.

**Week 6: Polish + Quebec.**
16. French translations (professional, not LLM).
17. French PDF template.
18. Quebec-specific assemblies and audit rules.
19. Mobile pass.

**Week 7: Closed beta with 3–5 electricians.**

**Week 8+: Iterate on what they actually need.**

Do not build voice, photos, integrations, or any cut feature until 10 paying contractors have asked for the same thing.

## 21. Definition of Done for v1

Ship when:

- A contractor can sign up, configure their business defaults, add a customer, type a job description, answer ≤4 clarifying questions, see a complete estimate with audit results, edit line items, and download a branded PDF in the correct language — all on a phone, in under 5 minutes, on a 4G connection.
- The 10 reference estimates produce identical numbers to the electrician’s hand calculations (±$5 for rounding).
- The audit catches a deliberately underbid quote in 100% of test cases.
- One real Quebec electrician has signed off on French terminology in the assembly library and PDF.

## 22. Things the Coding Agent Will Want to Add (and Shouldn’t)

- “Let me add an integration test framework.” Use pytest. Done.
- “Should I add a feature flag system?” No.
- “What about a CI/CD pipeline?” GitHub Actions: lint + test on PR, deploy on merge to main. Nothing else.
- “Should I add type generation for the frontend?” Yes — generate from OpenAPI. One step.
- “Should I add a state machine for quote status?” No, an enum and a few guard clauses are enough.
- “Should I use a queue for the LLM calls?” No. FastAPI background tasks. Synchronous request from the frontend, with streaming if needed.
- “Should I add internationalization for Spanish?” No.
- “Should I make the assembly library editable via admin UI?” No. YAML in git.

## 23. Open Questions to Resolve Before Coding

These are real decisions the founder needs to make. The coding agent should ask, not guess.

1. **Subscription pricing model.** Per-quote, per-month-flat, freemium? Affects metering architecture.
1. **Quote numbering scheme.** Per-contractor sequential? Year-prefixed? Confirm.
1. **Quote expiry default.** 14, 30, or 60 days?
1. **Whether to support multi-location contractors in v1.** (Recommended: no.)
1. **Whether to auto-email the quote to the customer** in v1 or just generate the PDF for the contractor to send manually. (Recommended: generate only, no email send.)
1. **Logo upload storage.** S3, Railway volume, or base64 in DB. (Recommended: S3-compatible bucket via Backblaze B2 for cost; or Railway volume if simpler.)

-----

## End of Build Prompt

Implementation notes for the coding agent:

- Ask before deviating from any architectural principle in §3.
- Surface decisions that aren’t covered here rather than guessing.
- Build the engine before the LLM. Test the engine before the UI. Test the audit before the PDF. Ship the PDF before the dashboard.
- If a feature feels easy to add but isn’t in §4, it goes in §5.