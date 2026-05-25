"""WeasyPrint PDF rendering (§14).

Two customer templates (EN/FR) and one internal contractor template. All
monetary/date values are pre-formatted in the build context so the templates
stay pure presentation. Customer line items combine material + labour per line;
the internal template shows the full breakdown, code refs, and audit history.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from quoteforge_api.assemblies.loader import get_library
from quoteforge_api.assemblies.schema import Category
from quoteforge_api.code_editions import get_code_matrix
from quoteforge_api.models import Customer, Quote, User
from quoteforge_api.models.enums import LineSource
from quoteforge_api.services import logos
from quoteforge_api.services.pdf.formatting import format_currency, format_date, format_pct
from quoteforge_api.services.tax.engine import compute_taxes

_TEMPLATES = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(default=True, default_for_string=True),
)
_CSS = (_TEMPLATES / "_styles.css").read_text(encoding="utf-8")

_CATEGORY_LABELS: dict[Category, dict[str, str]] = {
    Category.SERVICE: {"en": "Service & panels", "fr": "Branchement et panneaux"},
    Category.PANELS: {"en": "Panels", "fr": "Panneaux"},
    Category.CIRCUITS: {"en": "Circuits", "fr": "Circuits"},
    Category.DEVICES: {"en": "Devices", "fr": "Appareillage"},
    Category.LIGHTING: {"en": "Lighting", "fr": "Éclairage"},
    Category.EV: {"en": "EV charging", "fr": "Recharge de VÉ"},
    Category.SAFETY: {"en": "Safety", "fr": "Sécurité"},
    Category.EXTERIOR: {"en": "Exterior", "fr": "Extérieur"},
    Category.TROUBLESHOOTING: {"en": "Troubleshooting", "fr": "Dépannage"},
    Category.SPECIAL: {"en": "Special", "fr": "Travaux spéciaux"},
}
_PERMIT_LABEL = {"en": "Permits & fees", "fr": "Permis et frais"}
_OTHER_LABEL = {"en": "Additional work", "fr": "Travaux supplémentaires"}

_GST_LABEL = {"en": "GST", "fr": "TPS"}

_TERMS = {
    "en": (
        "This quotation is valid until the date shown above. Prices are in Canadian "
        "dollars. Work will be performed in accordance with the applicable provincial "
        "electrical code. Permit fees are passed through at cost. A signed acceptance "
        "is required before work begins."
    ),
    "fr": (
        "Cette soumission est valide jusqu'à la date indiquée ci-dessus. Les prix sont "
        "en dollars canadiens. Les travaux seront réalisés conformément au code "
        "électrique provincial applicable. Les frais de permis sont facturés au coût. "
        "Une acceptation signée est requise avant le début des travaux."
    ),
}


def _paragraphs(text: str | None) -> list[str]:
    """Split scope prose into paragraphs for clean rendering (§24.5).

    The LLM separates topics with blank lines; we render one <p> each so the
    customer PDF never shows a single wall of text. Collapses runs of blank
    lines and trims surrounding whitespace.
    """
    if not text:
        return []
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n")]
    return [b for b in blocks if b]


def _line_groups(quote: Quote, lang: str) -> list[dict]:
    library = get_library()
    groups: dict[str, dict] = {}
    for li in quote.line_items:
        if li.source == LineSource.ASSEMBLY and li.assembly_id and li.assembly_id in library:
            label = _CATEGORY_LABELS[library.get(li.assembly_id).category][lang]
        elif li.source == LineSource.PERMIT:
            label = _PERMIT_LABEL[lang]
        else:
            label = _OTHER_LABEL[lang]
        group = groups.setdefault(label, {"label": label, "lines": []})
        description = li.description_fr if lang == "fr" else li.description_en
        group["lines"].append({
            "description": description or li.description_en,
            "quantity": str(li.quantity.normalize()),
            "total": format_currency(li.line_total_cad, lang),
        })
    return list(groups.values())


def _tax_lines(quote: Quote, lang: str) -> list[dict]:
    breakdown = compute_taxes(
        quote.province,
        quote.subtotal_materials_cad,
        quote.subtotal_labor_cad + quote.subtotal_other_cad,
    )
    lines: list[dict] = []
    if breakdown.gst_cad > 0:
        lines.append({
            "label": _GST_LABEL[lang],
            "rate": format_pct(breakdown.gst_rate, lang),
            "amount": format_currency(breakdown.gst_cad, lang),
        })
    if breakdown.pst_qst_hst_cad > 0 or breakdown.pst_qst_hst_rate > 0:
        label = breakdown.pst_qst_hst_label_fr if lang == "fr" else breakdown.pst_qst_hst_label_en
        lines.append({
            "label": label,
            "rate": format_pct(breakdown.pst_qst_hst_rate, lang),
            "amount": format_currency(breakdown.pst_qst_hst_cad, lang),
        })
    return lines


def _contractor_block(user: User) -> dict:
    licences = []
    if user.esa_license_number:
        licences.append(f"ESA #{user.esa_license_number}")
    if user.rbq_license_number:
        licences.append(f"RBQ #{user.rbq_license_number}")
    if user.cmeq_membership_number:
        licences.append(f"CMEQ #{user.cmeq_membership_number}")
    # Resolve a stored logo to a file:// URI so WeasyPrint reads the bytes
    # directly; otherwise fall back to whatever logo_url holds (e.g. an http URL).
    local_logo = logos.logo_path(user.id)
    logo_src = local_logo.as_uri() if local_logo else user.logo_url

    address = ", ".join(
        p for p in [
            user.business_address_line1,
            user.business_address_line2,
            f"{user.business_city}, {user.province.value} {user.business_postal_code}"
            if user.business_city else None,
        ] if p
    )
    return {
        "business_name": user.business_name,
        "contact_name": user.full_name,
        "email": user.business_email or user.email,
        "phone": user.business_phone,
        "address": address,
        "province": user.province.value,
        "licences": licences,
        "logo_url": logo_src,
        "primary_color": user.primary_color_hex or "#1a3e5c",
    }


def _customer_block(customer: Customer) -> dict:
    return {
        "name": customer.name,
        "company": customer.company,
        "email": customer.email,
        "phone": customer.phone,
        "address_line1": customer.address_line1,
        "address_line2": customer.address_line2,
        "city": customer.city,
        "province": customer.province.value,
        "postal_code": customer.postal_code,
    }


def _terms(user: User, lang: str) -> str:
    """The contractor's editable terms in ``lang``, or the built-in default."""
    custom = user.terms_fr if lang == "fr" else user.terms_en
    return (custom or "").strip() or _TERMS[lang]


def _code_block(quote: Quote, lang: str) -> dict:
    """Province code context for the quote (edition locked at quote time + the
    regulator/permit model/utility from the code matrix), in ``lang``."""
    pc = get_code_matrix().get(quote.province)
    return {
        "edition": quote.code_edition,
        "regulator": pc.regulator.text(lang),
        "permit_model": pc.permit_model.text(lang),
        "utility": pc.utility,
    }


def _customer_context(quote: Quote, user: User, customer: Customer, lang: str) -> dict:
    scope = quote.customer_facing_scope_fr if lang == "fr" else quote.customer_facing_scope_en
    subtotal = (
        quote.subtotal_materials_cad
        + quote.subtotal_labor_cad
        + quote.subtotal_permits_cad
        + quote.subtotal_other_cad
    )
    return {
        "lang": lang,
        "styles": _CSS,
        "contractor": _contractor_block(user),
        "customer": _customer_block(customer),
        "quote_number": quote.quote_number,
        "issue_date": format_date(quote.created_at.date() if quote.created_at else None, lang),
        "valid_until": format_date(quote.valid_until, lang),
        "job_title": quote.job_title,
        "job_site_address": quote.job_site_address,
        "scope": scope or quote.job_description,
        "scope_paragraphs": _paragraphs(scope or quote.job_description),
        "groups": _line_groups(quote, lang),
        "subtotal": format_currency(subtotal, lang),
        "tax_lines": _tax_lines(quote, lang),
        "total": format_currency(quote.total_cad, lang),
        "terms": _terms(user, lang),
        "code_edition": quote.code_edition,
        "code": _code_block(quote, lang),
    }


def render_customer_pdf(quote: Quote, user: User, customer: Customer) -> bytes:
    lang = quote.customer_language.value
    template = _env.get_template(f"quote_{lang}.html.jinja")
    html = template.render(**_customer_context(quote, user, customer, lang))
    return HTML(string=html, base_url=str(_TEMPLATES)).write_pdf()


def render_internal_pdf(quote: Quote, user: User, customer: Customer) -> bytes:
    items = [
        {
            "line_number": li.line_number,
            "source": li.source.value,
            "assembly_id": li.assembly_id or "—",
            "description": li.description_en,
            "quantity": str(li.quantity.normalize()),
            "materials": format_currency(li.materials_cost_cad, "en"),
            "labor_hours": str(li.labor_hours.normalize()),
            "labor": format_currency(li.labor_cost_cad, "en"),
            "total": format_currency(li.line_total_cad, "en"),
            "code_refs": li.code_refs or [],
        }
        for li in quote.line_items
    ]
    flags = [
        {
            "severity": f.severity.value,
            "code": f.code,
            "message": f.message_en,
            "suggested_action": f.suggested_action,
            "overridden": f.overridden,
        }
        for f in quote.audit_flags
    ]
    context = {
        "lang": "en",
        "styles": _CSS,
        "contractor": _contractor_block(user),
        "customer": _customer_block(customer),
        "quote_number": quote.quote_number,
        "issue_date": format_date(quote.created_at.date() if quote.created_at else None, "en"),
        "province": quote.province.value,
        "code_edition": quote.code_edition,
        "code": _code_block(quote, "en"),
        "job_title": quote.job_title,
        "job_description": quote.job_description,
        "internal_notes": quote.internal_notes,
        "items": items,
        "subtotal_materials": format_currency(quote.subtotal_materials_cad, "en"),
        "subtotal_labor": format_currency(quote.subtotal_labor_cad, "en"),
        "subtotal_permits": format_currency(quote.subtotal_permits_cad, "en"),
        "subtotal_other": format_currency(quote.subtotal_other_cad, "en"),
        "total": format_currency(quote.total_cad, "en"),
        "gross_margin_pct": str(quote.gross_margin_pct),
        "flags": flags,
        "audit_passed": quote.audit_passed,
    }
    template = _env.get_template("internal_quote.html.jinja")
    return HTML(string=template.render(**context), base_url=str(_TEMPLATES)).write_pdf()
