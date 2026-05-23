import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useQuotes } from "../api/hooks";
import type { QuoteStatus } from "../api/types";
import { Badge, PageHeader, Spinner } from "../components/ui";
import { money, percent } from "../lib/format";

const tone: Record<QuoteStatus, "gray" | "blue" | "green" | "red" | "amber"> = {
  draft: "gray",
  sent: "blue",
  approved: "green",
  declined: "red",
  expired: "amber",
};

export default function Quotes() {
  const { t, i18n } = useTranslation();
  const { data, isLoading } = useQuotes();

  return (
    <div>
      <PageHeader
        title={t("quotes.title")}
        action={<Link to="/quotes/new" className="btn-primary">{t("quotes.new")}</Link>}
      />
      {isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : data && data.length > 0 ? (
        <div className="grid gap-3">
          {data.map((q) => (
            <Link key={q.id} to={`/quotes/${q.id}`} className="card flex items-center justify-between hover:border-brand">
              <div>
                <div className="font-semibold">{q.quote_number} · {q.job_title}</div>
                <div className="mt-1"><Badge tone={tone[q.status]}>{t(`status.${q.status}`)}</Badge></div>
              </div>
              <div className="text-right">
                <div className="font-semibold">{money(q.total_cad, i18n.language)}</div>
                <div className="text-sm text-gray-500">{t("quotes.margin")}: {percent(q.gross_margin_pct, i18n.language)}</div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-gray-500">{t("quotes.empty")}</p>
      )}
    </div>
  );
}
