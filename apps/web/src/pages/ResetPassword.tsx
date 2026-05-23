import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { Field, Spinner } from "../components/ui";

export default function ResetPassword() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/auth/password-reset/confirm", { token, new_password: password }, false);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <form onSubmit={submit} className="card">
        <h2 className="mb-4 text-lg font-semibold">{t("auth.reset")}</h2>
        {done ? (
          <p className="text-sm text-green-700">{t("auth.resetDone")}</p>
        ) : (
          <>
            {error && <p className="field-error mb-3">{error}</p>}
            <Field label="Token">
              <input className="input" value={token} onChange={(e) => setToken(e.target.value)} required />
            </Field>
            <Field label={t("auth.newPassword")}>
              <input className="input" type="password" value={password}
                     onChange={(e) => setPassword(e.target.value)} required minLength={10} />
            </Field>
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? <Spinner /> : t("auth.reset")}
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
