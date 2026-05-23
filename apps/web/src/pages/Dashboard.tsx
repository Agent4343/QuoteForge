import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useDashboard, useQuotes } from "../api/hooks";
import { PageHeader, Spinner } from "../components/ui";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-brand">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const stats = useDashboard();
  const quotes = useQuotes();

  if (stats.isLoading) return <Spinner label={t("common.loading")} />;
  const s = stats.data;

  const counts: Record<string, number> = {};
  for (const q of quotes.data ?? []) counts[q.status] = (counts[q.status] ?? 0) + 1;
  const chartData = ["draft", "sent", "approved", "declined", "expired"].map((st) => ({
    status: t(`status.${st}`),
    count: counts[st] ?? 0,
  }));
  const hasData = (quotes.data?.length ?? 0) > 0;

  return (
    <div>
      <PageHeader title={t("dashboard.title")} />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label={t("dashboard.openQuotes")} value={String(s?.open_quotes ?? 0)} />
        <Stat label={t("dashboard.winRate")} value={s?.win_rate_pct != null ? `${s.win_rate_pct}%` : "—"} />
        <Stat label={t("dashboard.avgMargin")} value={s?.average_margin_pct != null ? `${s.average_margin_pct}%` : "—"} />
      </div>

      <div className="card mt-6">
        <h2 className="mb-3 font-semibold">{t("dashboard.byStatus")}</h2>
        {hasData ? (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="status" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Bar dataKey="count" fill="#1a3e5c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-gray-500">{t("dashboard.none")}</p>
        )}
      </div>
    </div>
  );
}
