import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { ApiError, api, fetchPdf } from "../api/client";
import { useQuote, useQuoteActions } from "../api/hooks";
import type { QuoteLineItemIn, QuoteLineItemOut, QuoteOut } from "../api/types";
import { Badge, PageHeader, Spinner } from "../components/ui";
import { errorMessage } from "../lib/errors";
import { money, percent } from "../lib/format";

interface AssemblyIndexItem {
  id: string;
  category: string;
  names: { en: string; fr: string };
}

function useAssemblies() {
  return useQuery({
    queryKey: ["assemblies"],
    queryFn: () => api.get<{ assemblies: AssemblyIndexItem[] }>("/api/assemblies"),
  });
}

function isGenerated(li: QuoteLineItemOut): boolean {
  return !!(li.parameters && (li.parameters as Record<string, unknown>)["_generated"]);
}

function toInput(lines: QuoteLineItemOut[]): QuoteLineItemIn[] {
  // Include every field; the API uses the ones relevant to `source`. Generated
  // lines (e.g. the minimum call-out) are excluded — they are engine output.
  return lines
    .filter((l) => !isGenerated(l))
    .map(
      (l): QuoteLineItemIn => ({
        source: l.source,
        assembly_id: l.source === "assembly" ? l.assembly_id : undefined,
        quantity: l.quantity,
        parameters: (l.parameters ?? {}) as { [key: string]: unknown },
        description_en: l.description_en,
        description_fr: l.description_fr,
        amount_cad: l.line_total_cad,
        labor_hours: l.labor_hours,
      }),
    );
}

/* ---------------- Chat pane ---------------- */
function ChatPane({ quote, id }: { quote: QuoteOut; id: string }) {
  const { t } = useTranslation();
  const { generate, answer } = useQuoteActions(id);
  type Msg = { who: "you" | "ai" | "sys"; text: string };
  const [log, setLog] = useState<Msg[]>([]);
  const [input, setInput] = useState(quote.job_description ?? "");
  const [question, setQuestion] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  const busy = generate.isPending || answer.isPending;

  const handleResult = (r: { status: string; question?: Record<string, unknown> | null; assistant_text?: string }) => {
    if (r.status === "question") {
      const q = r.question ?? null;
      setQuestion(q);
      const why = q && q["why_it_matters"] ? `\n${String(q["why_it_matters"])}` : "";
      setLog((l) => [...l, { who: "ai", text: (q ? String(q["question"] ?? "") : "") + why || "(needs more detail)" }]);
    } else {
      setQuestion(null);
      setLog((l) => [...l, { who: "ai", text: r.assistant_text || "Updated the estimate — see the middle and preview panes." }]);
    }
  };

  const send = () => {
    const text = input.trim();
    if (!text) return;
    setError("");
    setInput("");
    setLog((l) => [...l, { who: "you", text }]);
    const opts = {
      onSuccess: handleResult,
      onError: (e: unknown) => {
        const m = errorMessage(e);
        setError(m);
        setLog((l) => [...l, { who: "sys", text: m }]);
      },
    };
    // A pending question must be answered as a tool result; otherwise the text
    // is a new message that continues the same conversation (refining the quote).
    if (question) answer.mutate({ answer: text }, opts);
    else generate.mutate({ job_description: text }, opts);
  };

  return (
    <div className="card">
      <h2 className="mb-2 font-semibold">{t("quotes.chat")}</h2>

      <div className="mb-3 max-h-[360px] space-y-2 overflow-y-auto">
        {log.length === 0 && <p className="text-sm text-gray-500">{t("quotes.jobDescription")}</p>}
        {log.map((m, i) => (
          <div key={i} className={m.who === "you" ? "text-right" : ""}>
            <span
              className={
                "inline-block max-w-[90%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm " +
                (m.who === "you"
                  ? "bg-brand text-white"
                  : m.who === "ai"
                    ? "bg-gray-100 text-gray-800"
                    : "bg-red-50 text-red-700")
              }
            >
              {m.text}
            </span>
          </div>
        ))}
        {busy && <Spinner label={t("quotes.generating")} />}
      </div>

      <textarea
        className="input min-h-[70px] py-2"
        placeholder={question ? t("quotes.answer") : t("quotes.jobDescription")}
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />
      <button className="btn-primary mt-2 w-full" onClick={send} disabled={busy || !input.trim()}>
        {busy ? <Spinner label={t("quotes.generating")} /> : question ? t("quotes.answer") : t("quotes.generate")}
      </button>
      {error && <p className="field-error mt-2">{error}</p>}
    </div>
  );
}

/* ---------------- Estimate pane ---------------- */
function EstimatePane({ quote, id }: { quote: QuoteOut; id: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { update, recompute, overrideFlag } = useQuoteActions(id);
  const assemblies = useAssemblies();
  const [lines, setLines] = useState<QuoteLineItemOut[]>(quote.line_items);
  const [addId, setAddId] = useState("");

  useEffect(() => setLines(quote.line_items), [quote.line_items]);

  const setQty = (idx: number, qty: string) =>
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, quantity: qty } : l)));
  const removeLine = (idx: number) => setLines((ls) => ls.filter((_, i) => i !== idx));
  const addAssembly = () => {
    if (!addId) return;
    const a = assemblies.data?.assemblies.find((x) => x.id === addId);
    setLines((ls) => [
      ...ls,
      {
        id: `new-${Date.now()}`,
        line_number: ls.length + 1,
        source: "assembly",
        assembly_id: addId,
        description_en: a?.names.en ?? addId,
        description_fr: a?.names.fr ?? addId,
        quantity: "1",
        parameters: {},
        materials_cost_cad: "0",
        labor_hours: "0",
        labor_cost_cad: "0",
        line_total_cad: "0",
        code_refs: [],
      } as QuoteLineItemOut,
    ]);
    setAddId("");
  };
  const save = () => update.mutate({ line_items: toInput(lines) });

  return (
    <div className="card">
      <h2 className="mb-2 font-semibold">{t("quotes.estimate")}</h2>

      <div className="divide-y divide-gray-100">
        {lines.map((l, idx) => (
          <div key={l.id} className="flex items-center gap-2 py-2">
            <div className="flex-1">
              <div className="text-sm">{lang === "fr" ? l.description_fr : l.description_en}</div>
              {l.assembly_id && <div className="text-xs text-gray-400">{l.assembly_id}</div>}
            </div>
            {l.source === "assembly" && !isGenerated(l) ? (
              <input
                className="input w-16 text-center"
                inputMode="decimal"
                value={l.quantity}
                onChange={(e) => setQty(idx, e.target.value)}
                aria-label={t("quotes.qty")}
              />
            ) : (
              <span className="w-16 text-center text-sm text-gray-400">{l.quantity}</span>
            )}
            <span className="w-24 text-right text-sm">{money(l.line_total_cad, lang)}</span>
            {!isGenerated(l) && (
              <button className="text-red-500 px-2" onClick={() => removeLine(idx)} aria-label={t("quotes.remove")}>
                ×
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <select className="input flex-1" aria-label={t("quotes.addLine")} value={addId}
                onChange={(e) => setAddId(e.target.value)}>
          <option value="">{t("quotes.addLine")}…</option>
          {assemblies.data?.assemblies.map((a) => (
            <option key={a.id} value={a.id}>{lang === "fr" ? a.names.fr : a.names.en}</option>
          ))}
        </select>
        <button className="btn-secondary" onClick={addAssembly} disabled={!addId}>+</button>
      </div>

      <button className="btn-primary mt-3 w-full" onClick={save} disabled={update.isPending}>
        {update.isPending || recompute.isPending ? <Spinner /> : t("quotes.recompute")}
      </button>

      <dl className="mt-4 space-y-1 text-sm">
        <Row label={t("quotes.materials")} value={money(quote.subtotal_materials_cad, lang)} />
        <Row label={t("quotes.labour")} value={money(quote.subtotal_labor_cad, lang)} />
        {Number(quote.subtotal_permits_cad) > 0 && (
          <Row label={t("quotes.permits")} value={money(quote.subtotal_permits_cad, lang)} />
        )}
        <Row label={t("quotes.tax")} value={money(Number(quote.tax_gst_cad) + Number(quote.tax_pst_qst_hst_cad), lang)} />
        <div className="flex justify-between border-t pt-2 text-base font-bold">
          <span>{t("quotes.total")}</span>
          <span>{money(quote.total_cad, lang)}</span>
        </div>
        <Row label={t("quotes.margin")} value={percent(quote.gross_margin_pct, lang)} />
      </dl>

      <h3 className="mt-4 mb-2 text-sm font-semibold">{t("quotes.auditFlags")}</h3>
      {quote.audit_flags.length === 0 ? (
        <p className="text-sm text-gray-500">{t("quotes.noFlags")}</p>
      ) : (
        <div className="space-y-2">
          {quote.audit_flags.map((f) => (
            <div key={f.id} className="rounded-lg border border-gray-200 p-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={f.severity === "critical" ? "red" : f.severity === "warn" ? "amber" : "blue"}>
                  {f.severity}
                </Badge>
                {f.severity === "critical" && !f.overridden && (
                  <button className="btn-secondary px-3 py-1 text-xs" onClick={() => overrideFlag.mutate(f.id)}>
                    {t("quotes.override")}
                  </button>
                )}
                {f.overridden && <span className="text-xs text-gray-400">✓</span>}
              </div>
              <p className="mt-1">{lang === "fr" ? f.message_fr : f.message_en}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span>{value}</span>
    </div>
  );
}

/* ---------------- Preview pane ---------------- */
function PreviewPane({ quote, id }: { quote: QuoteOut; id: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { send, finalize, markStatus } = useQuoteActions(id);
  const [error, setError] = useState("");
  const scope = lang === "fr" ? quote.customer_facing_scope_fr : quote.customer_facing_scope_en;

  const act = (m: { mutate: (v: undefined, o: object) => void }) =>
    m.mutate(undefined, {
      onError: (e: unknown) => setError(e instanceof ApiError ? String(e.detail) : t("common.error")),
      onSuccess: () => setError(""),
    });

  const openInternal = async () => {
    const url = await fetchPdf(`/api/quotes/${id}/pdf?variant=internal`);
    window.open(url, "_blank");
  };

  return (
    <div className="card">
      <h2 className="mb-2 font-semibold">{t("quotes.preview")}</h2>
      <div className="rounded-lg bg-gray-50 p-3 text-sm">
        <div className="font-semibold">{quote.quote_number}</div>
        <p className="mt-2 whitespace-pre-wrap">{scope || t("quotes.noScope")}</p>
      </div>

      {quote.pdf_blocked && <p className="field-error mt-3">{t("quotes.pdfBlocked")}</p>}
      {error && <p className="field-error mt-3">{error}</p>}

      <div className="mt-3 grid gap-2">
        <a
          className={`btn-secondary ${quote.pdf_blocked ? "pointer-events-none opacity-50" : ""}`}
          href={`/quotes/${id}/pdf-preview`}
        >
          {t("quotes.downloadPdf")}
        </a>
        <button className="btn-secondary" onClick={openInternal}>{t("quotes.internalPdf")}</button>
        <button className="btn-secondary" onClick={() => act(finalize)} disabled={finalize.isPending}>
          {t("quotes.finalize")}
        </button>
        <button className="btn-primary" onClick={() => act(send)} disabled={send.isPending}>
          {t("quotes.send")}
        </button>
        <select
          className="input"
          aria-label={t("quotes.markStatus")}
          value={quote.status}
          onChange={(e) => markStatus.mutate(e.target.value)}
        >
          {["draft", "sent", "approved", "declined", "expired"].map((s) => (
            <option key={s} value={s}>{t(`status.${s}`)}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

/* ---------------- Builder ---------------- */
export default function QuoteBuilder() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const { data: quote, isLoading } = useQuote(id);
  const [tab, setTab] = useState<"chat" | "estimate" | "preview">("estimate");

  if (isLoading || !quote) return <Spinner label={t("common.loading")} />;

  const tabs = [
    { key: "chat" as const, label: t("quotes.chat") },
    { key: "estimate" as const, label: t("quotes.estimate") },
    { key: "preview" as const, label: t("quotes.preview") },
  ];

  return (
    <div>
      <PageHeader title={`${quote.quote_number} · ${quote.job_title}`} />

      {/* Mobile: tabs. Desktop: three columns. */}
      <div className="mb-4 flex gap-1 lg:hidden">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium ${
              tab === tb.key ? "bg-brand text-white" : "bg-white text-gray-600 border border-gray-200"
            }`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className={tab === "chat" ? "" : "hidden lg:block"}>
          <ChatPane quote={quote} id={id} />
        </div>
        <div className={tab === "estimate" ? "" : "hidden lg:block"}>
          <EstimatePane quote={quote} id={id} />
        </div>
        <div className={tab === "preview" ? "" : "hidden lg:block"}>
          <PreviewPane quote={quote} id={id} />
        </div>
      </div>
    </div>
  );
}
