// CAD currency / date formatting via Intl (§17). Locale follows the UI language.

function locale(lang: string): string {
  return lang === "fr" ? "fr-CA" : "en-CA";
}

export function money(value: string | number | null | undefined, lang: string): string {
  const n = typeof value === "string" ? Number(value) : value ?? 0;
  return new Intl.NumberFormat(locale(lang), { style: "currency", currency: "CAD" }).format(n || 0);
}

export function percent(value: string | number | null | undefined, lang: string): string {
  const n = typeof value === "string" ? Number(value) : value ?? 0;
  return new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 2 }).format(n || 0) + " %";
}

export function formatDate(iso: string | null | undefined, lang: string): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(locale(lang), { dateStyle: "medium" }).format(new Date(iso));
}
