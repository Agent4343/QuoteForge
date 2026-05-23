import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Field, Spinner } from "../components/ui";

export default function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/api/auth/password-reset/request", { email }, false);
      setSent(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <form onSubmit={submit} className="card">
        <h2 className="mb-4 text-lg font-semibold">{t("auth.reset")}</h2>
        {sent ? (
          <p className="text-sm text-green-700">{t("auth.resetSent")}</p>
        ) : (
          <>
            <Field label={t("auth.email")}>
              <input className="input" type="email" inputMode="email"
                     value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? <Spinner /> : t("auth.sendReset")}
            </button>
          </>
        )}
        <div className="mt-4 text-sm">
          <Link className="text-brand" to="/login">{t("auth.login")}</Link>
        </div>
      </form>
    </div>
  );
}
