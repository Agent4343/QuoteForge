import { useTranslation } from "react-i18next";
import { useCodeEditions } from "../api/hooks";
import type { ProvinceCode } from "../api/hooks";
import { Badge, PageHeader, Spinner } from "../components/ui";
import { formatDate } from "../lib/format";

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex gap-2 py-1 text-sm">
      <span className="w-28 shrink-0 text-gray-500">{label}</span>
      <span className="text-gray-800">{value}</span>
    </div>
  );
}

export default function CodeReference() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { data, isLoading } = useCodeEditions();
  const today = new Date().toISOString().slice(0, 10);

  const inTransition = (pc: ProvinceCode) =>
    !!pc.transition && pc.transition.start <= today && today <= pc.transition.end;

  return (
    <div>
      <PageHeader title={t("code.title")} />
      <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        {t("code.disclaimer")}
      </p>

      {isLoading || !data ? (
        <Spinner label={t("common.loading")} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(data.provinces).map(([code, pc]) => (
            <div key={code} className="card">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-bold text-brand">{code}</h2>
                {inTransition(pc) && <Badge tone="amber">{t("code.transitioning")}</Badge>}
              </div>
              <Row label={t("code.current")} value={pc.current_edition.label} />
              {pc.pending_edition && (
                <Row label={t("code.pending")} value={pc.pending_edition.label} />
              )}
              {pc.transition && (
                <Row
                  label={t("code.transition")}
                  value={`${formatDate(pc.transition.start, lang)} – ${formatDate(pc.transition.end, lang)}`}
                />
              )}
              <Row label={t("code.regulator")} value={pc.regulator} />
              <Row label={t("code.permit")} value={pc.permit_model} />
              <Row label={t("code.utility")} value={pc.utility} />
              <Row label={t("code.language")} value={pc.customer_language_default.toUpperCase()} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
