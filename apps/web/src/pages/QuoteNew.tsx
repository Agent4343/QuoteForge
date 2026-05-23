import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useCreateQuote, useCustomers } from "../api/hooks";
import { Field, PageHeader, Spinner } from "../components/ui";

export default function QuoteNew() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const customers = useCustomers();
  const create = useCreateQuote();
  const [customerId, setCustomerId] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [error, setError] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    create.mutate(
      { customer_id: customerId, job_title: jobTitle, job_description: jobDescription },
      {
        onSuccess: (q) => navigate(`/quotes/${q.id}`),
        onError: (err) => setError(err instanceof ApiError ? String(err.detail) : t("common.error")),
      },
    );
  };

  const hasCustomers = (customers.data?.length ?? 0) > 0;

  return (
    <div className="max-w-xl">
      <PageHeader title={t("quotes.new")} />
      {!hasCustomers && !customers.isLoading ? (
        <div className="card">
          <p className="mb-3 text-gray-600">{t("customers.empty")}</p>
          <Link to="/customers/new" className="btn-primary">{t("customers.new")}</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="card">
          {error && <p className="field-error mb-3">{error}</p>}
          <Field label={t("quotes.customer")}>
            <select className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
              <option value="">{t("quotes.selectCustomer")}</option>
              {customers.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.name} — {c.city}, {c.province}</option>
              ))}
            </select>
          </Field>
          <Field label={t("quotes.jobTitle")}>
            <input className="input" value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} required />
          </Field>
          <Field label={t("quotes.jobDescription")}>
            <textarea className="input min-h-[120px] py-2" value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)} />
          </Field>
          <button className="btn-primary w-full" disabled={create.isPending || !customerId}>
            {create.isPending ? <Spinner /> : t("quotes.create")}
          </button>
        </form>
      )}
    </div>
  );
}
