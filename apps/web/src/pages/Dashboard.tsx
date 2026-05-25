import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAssemblyMetrics, useDashboard, useQuotes } from "../api/hooks";
import { Badge, PageHeader, Spinner } from "../components/ui";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-brand">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const stats = useDashboard();
  const quotes = useQuotes();
  const assemblies = useAssemblyMetrics();

  if (stats.isLoading) return <Spinner label={t("common.loading")} />;
  const s = stats.data;
  const usage = assemblies.data?.assemblies ?? [];

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

      <div className="card mt-4">
        <h2 className="mb-1 font-semibold">{t("dashboard.aiUsage")}</h2>
        <div className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
          <span>
            <span className="text-gray-500">{t("dashboard.aiCost")}: </span>
            <span className="font-semibold text-brand">
              {new Intl.NumberFormat(i18n.language === "fr" ? "fr-CA" : "en-CA", {
                style: "currency",
                currency: "CAD",
              }).format(s?.llm_cost_cad ?? 0)}
            </span>
          </span>
          <span>
            <span className="text-gray-500">{t("dashboard.aiQuotes")}: </span>
            <span className="font-semibold">{s?.ai_sessions ?? 0}</span>
          </span>
          <span className="text-gray-400">
            {(s?.llm_input_tokens ?? 0) + (s?.llm_output_tokens ?? 0)} tokens
          </span>
        </div>
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

      <div className="card mt-6">
        <h2 className="mb-1 font-semibold">{t("dashboard.assemblyUsage")}</h2>
        <p className="mb-3 text-xs text-gray-400">{t("dashboard.editRateHint")}</p>
        {usage.length === 0 ? (
          <p className="text-sm text-gray-500">{t("dashboard.noAssemblyUsage")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500">
                  <th className="py-2 pr-2 font-medium">{t("dashboard.assembly")}</th>
                  <th className="py-2 px-2 text-right font-medium">{t("dashboard.uses")}</th>
                  <th className="py-2 px-2 text-right font-medium">{t("dashboard.quotes")}</th>
                  <th className="py-2 pl-2 text-right font-medium">{t("dashboard.editRate")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {usage.map((a) => (
                  <tr key={a.assembly_id}>
                    <td className="py-2 pr-2">
                      <div className="flex items-center gap-2">
                        <span>{lang === "fr" ? a.name_fr : a.name_en}</span>
                        {a.status !== "reviewed" && <Badge tone="amber">{a.status}</Badge>}
                      </div>
                      <div className="text-xs text-gray-400">{a.assembly_id}</div>
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">{a.line_count}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{a.quote_count}</td>
                    <td className="py-2 pl-2 text-right tabular-nums">
                      <span className={a.edit_rate_pct >= 50 ? "font-semibold text-amber-600" : "text-gray-600"}>
                        {a.edit_rate_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
