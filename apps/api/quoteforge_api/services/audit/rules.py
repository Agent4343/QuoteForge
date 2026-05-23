"""Audit rules (§10). Each rule is a pure function: (context) -> list[AuditFlag].

Pure Python, no LLM. Critical flags block PDF generation until overridden.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from quoteforge_api.assemblies.schema import Assembly, Category
from quoteforge_api.money import ZERO, D
from quoteforge_api.provinces import Province
from quoteforge_api.services.audit.types import AuditContext, AuditFlag
from quoteforge_api.services.estimating.engine import effective_materials, unit_labor_hours

# Quebec code transition window (§3.4).
QC_TRANSITION_START = date(2026, 3, 26)
QC_TRANSITION_END = date(2026, 9, 26)

_SCOPE_CREEP_PHRASES = [
    "might need", "may need", "while you're at it", "while we're at it",
    "depending on what we find", "if needed", "if required", "as required",
    "tbd", "to be determined", "not sure if",
    # FR
    "peut-être", "si nécessaire", "au besoin", "selon ce qu'on trouve",
    "à déterminer",
]


def _service_change_assemblies(ctx: AuditContext) -> list[Assembly]:
    out = []
    for req in ctx.requested_assemblies:
        a = ctx.library.get(req.assembly_id)
        if a.category in {Category.SERVICE, Category.PANELS}:
            out.append(a)
    return out


def _has_category(ctx: AuditContext, category: Category) -> bool:
    return any(ctx.library.get(r.assembly_id).category == category for r in ctx.requested_assemblies)


def _has_afci(ctx: AuditContext) -> bool:
    return any("afci" in r.assembly_id for r in ctx.requested_assemblies)


def _total_labor_hours(ctx: AuditContext) -> Decimal:
    return sum((li.labor_hours for li in ctx.estimate.line_items), ZERO)


# --- missing_items ---------------------------------------------------------

def requires_permit_when_service_change(ctx: AuditContext) -> list[AuditFlag]:
    if _service_change_assemblies(ctx) and ctx.estimate.subtotal_permits_cad <= ZERO:
        return [AuditFlag(
            "warn", "PERMIT_MISSING_SERVICE_CHANGE",
            "This estimate includes service/panel work but no permit fee.",
            "Cette estimation comprend des travaux de branchement ou de panneau, mais aucun frais de permis.",
            "Add the applicable ESA/RBQ or municipal permit, or confirm it is excluded.",
            "Ajoutez le permis ESA/RBQ ou municipal applicable, ou confirmez son exclusion.",
        )]
    return []


def afci_required_for_new_circuits_in_dwelling(ctx: AuditContext) -> list[AuditFlag]:
    if ctx.province == Province.ON and _has_category(ctx, Category.CIRCUITS) and not _has_afci(ctx):
        return [AuditFlag(
            "warn", "AFCI_MAY_BE_REQUIRED",
            "New dwelling-unit branch circuits may require AFCI protection (OESC 2024 Rule 26-724).",
            "Les nouveaux circuits de dérivation d'un logement peuvent exiger une protection AFCI "
            "(OESC 2024, règle 26-724).",
            "Confirm whether AFCI breakers are required and add them if so.",
            "Confirmez si des disjoncteurs AFCI sont requis et ajoutez-les le cas échéant.",
        )]
    return []


def travel_time_for_long_jobs(ctx: AuditContext) -> list[AuditFlag]:
    if _total_labor_hours(ctx) > D("4") and ctx.estimate.subtotal_other_cad <= ZERO:
        return [AuditFlag(
            "info", "TRAVEL_TIME_MISSING",
            "Job exceeds 4 labour hours but no travel/mobilization charge is present.",
            "Le travail dépasse 4 heures de main-d'œuvre, mais aucuns frais de déplacement ne sont indiqués.",
            "Consider adding travel time if it applies.",
            "Envisagez d'ajouter du temps de déplacement s'il y a lieu.",
        )]
    return []


def hq_coordination_for_qc_service_changes(ctx: AuditContext) -> list[AuditFlag]:
    if ctx.province == Province.QC and _service_change_assemblies(ctx):
        text = (ctx.customer_facing_scope + " " + ctx.job_description).lower()
        if "hydro" not in text:
            return [AuditFlag(
                "warn", "HQ_COORDINATION_MISSING",
                "Quebec service change without any mention of Hydro-Québec coordination.",
                "Changement de branchement au Québec sans mention de coordination avec Hydro-Québec.",
                "Confirm Hydro-Québec disconnect/reconnect coordination and reflect it in the scope.",
                "Confirmez la coordination de débranchement/rebranchement avec Hydro-Québec "
                "et indiquez-la dans la portée.",
            )]
    return []


# --- margin -----------------------------------------------------------------

def margin_below_minimum(ctx: AuditContext) -> list[AuditFlag]:
    if ctx.estimate.gross_margin_pct < ctx.contractor_minimum_margin_pct:
        return [AuditFlag(
            "critical", "MARGIN_BELOW_MIN",
            f"Gross margin {ctx.estimate.gross_margin_pct}% is below your minimum "
            f"of {ctx.contractor_minimum_margin_pct}%.",
            f"La marge brute de {ctx.estimate.gross_margin_pct}% est inférieure à votre "
            f"minimum de {ctx.contractor_minimum_margin_pct}%.",
            "Increase markup, reduce cost, or override to proceed at this margin.",
            "Augmentez la majoration, réduisez les coûts, ou passez outre pour continuer à cette marge.",
        )]
    return []


def labor_ratio_outside_band(ctx: AuditContext) -> list[AuditFlag]:
    work = ctx.estimate.subtotal_materials_cad + ctx.estimate.subtotal_labor_cad
    if work <= ZERO:
        return []
    labor_share = ctx.estimate.subtotal_labor_cad / work
    if labor_share < D("0.30"):
        return [AuditFlag(
            "warn", "LABOR_RATIO_LOW",
            f"Labour is only {(labor_share * 100).quantize(D('0.1'))}% of the work total — "
            "unusually low for service work.",
            f"La main-d'œuvre ne représente que {(labor_share * 100).quantize(D('0.1'))}% du total — "
            "inhabituellement bas pour des travaux de service.",
            "Verify labour hours were not under-counted.",
            "Vérifiez que les heures de main-d'œuvre n'ont pas été sous-estimées.",
        )]
    return []


# --- labor_plausibility -----------------------------------------------------

def labor_hours_outside_band_per_assembly(ctx: AuditContext) -> list[AuditFlag]:
    """Flag any assembly line whose (possibly contractor-edited) labour hours fall
    outside 70–150% of the engine-expected hours for that line."""
    flags: list[AuditFlag] = []
    for line in ctx.estimate.line_items:
        if line.source != "assembly" or line.assembly_id is None:
            continue
        assembly = ctx.library.get(line.assembly_id)
        expected = unit_labor_hours(assembly, line.parameters, ctx.province) * line.quantity
        if expected <= ZERO:
            continue
        actual = ctx.line_hours_override.get(line.line_number, line.labor_hours)
        if actual < expected * D("0.7") or actual > expected * D("1.5"):
            flags.append(AuditFlag(
                "warn", "LABOR_HOURS_OUTSIDE_BAND",
                f"{assembly.names.en}: {actual} h is outside 70–150% of the expected {expected} h.",
                f"{assembly.names.fr} : {actual} h se situe hors de la plage de 70 à 150% "
                f"des {expected} h prévues.",
                "Confirm the labour estimate for this item.",
                "Confirmez l'estimation de main-d'œuvre pour cet article.",
            ))
    return flags


# --- pricing ----------------------------------------------------------------

def stale_material_pricing(ctx: AuditContext) -> list[AuditFlag]:
    as_of = ctx.as_of or date.today()
    used: set[str] = set()
    for req in ctx.requested_assemblies:
        assembly = ctx.library.get(req.assembly_id)
        for m in effective_materials(assembly, ctx.province):
            used.add(m.sku)
    stale = sorted(s for s in ctx.pricebook.stale_skus(as_of) if s in used)
    if stale:
        return [AuditFlag(
            "warn", "STALE_PRICING",
            f"Material pricing is older than {ctx.pricebook.stale_after_days} days: "
            f"{', '.join(stale)}.",
            f"Les prix des matériaux datent de plus de {ctx.pricebook.stale_after_days} jours : "
            f"{', '.join(stale)}.",
            "Refresh prices from the supplier catalogue before sending.",
            "Mettez à jour les prix à partir du catalogue du fournisseur avant l'envoi.",
        )]
    return []


# --- scope_risk -------------------------------------------------------------

def scope_creep_language_in_description(ctx: AuditContext) -> list[AuditFlag]:
    text = ctx.job_description.lower()
    hits = [p for p in _SCOPE_CREEP_PHRASES if p in text]
    if hits:
        return [AuditFlag(
            "warn", "SCOPE_CREEP_LANGUAGE",
            f"The job description contains hedging language ({', '.join(hits[:3])}). "
            "Undefined scope is a common source of underbidding.",
            f"La description du travail contient un langage évasif ({', '.join(hits[:3])}). "
            "Une portée mal définie est une cause fréquente de sous-évaluation.",
            "Pin down the scope or add an allowance/exclusion before quoting.",
            "Précisez la portée ou ajoutez une provision/exclusion avant de soumissionner.",
        )]
    return []


# --- provincial_specific ----------------------------------------------------

def qc_customer_language_check(ctx: AuditContext) -> list[AuditFlag]:
    if ctx.customer_province == Province.QC and ctx.customer_language != "fr":
        return [AuditFlag(
            "warn", "QC_CUSTOMER_LANGUAGE",
            "Customer is in Quebec but the quote language is not French.",
            "Le client est au Québec, mais la langue de la soumission n'est pas le français.",
            "Set the customer-facing language to French unless the customer requested English.",
            "Réglez la langue destinée au client sur le français, sauf demande contraire du client.",
        )]
    return []


def qc_code_edition_transition_warning(ctx: AuditContext) -> list[AuditFlag]:
    if ctx.province == Province.QC and ctx.permit_date is not None:
        if QC_TRANSITION_START <= ctx.permit_date <= QC_TRANSITION_END:
            return [AuditFlag(
                "warn", "QC_CODE_TRANSITION",
                "Permit date falls in the Quebec code transition window "
                "(2026-03-26 to 2026-09-26). Confirm which code edition applies.",
                "La date du permis se situe dans la période de transition du code québécois "
                "(du 2026-03-26 au 2026-09-26). Confirmez l'édition du code applicable.",
                "Confirm CCÉ 2015 vs CCÉ 2021 (QC) with the contractor and lock it on the quote.",
                "Confirmez CCÉ 2015 ou CCÉ 2021 (QC) avec l'entrepreneur et verrouillez-la sur la soumission.",
            )]
    return []


def esa_notification_present_in_on_quote(ctx: AuditContext) -> list[AuditFlag]:
    if ctx.province == Province.ON and (
        _service_change_assemblies(ctx) or _has_category(ctx, Category.CIRCUITS)
    ):
        if "esa" not in ctx.customer_facing_scope.lower():
            return [AuditFlag(
                "warn", "ESA_NOTIFICATION_MISSING",
                "Ontario quote with permit-bearing work does not mention the ESA notification.",
                "Soumission ontarienne avec travaux soumis à permis ne mentionnant pas l'avis ESA.",
                "Reference the ESA notification/inspection in the customer scope.",
                "Mentionnez l'avis/inspection ESA dans la portée destinée au client.",
            )]
    return []


ALL_RULES = [
    requires_permit_when_service_change,
    afci_required_for_new_circuits_in_dwelling,
    travel_time_for_long_jobs,
    hq_coordination_for_qc_service_changes,
    margin_below_minimum,
    labor_ratio_outside_band,
    labor_hours_outside_band_per_assembly,
    stale_material_pricing,
    scope_creep_language_in_description,
    qc_customer_language_check,
    qc_code_edition_transition_warning,
    esa_notification_present_in_on_quote,
]
