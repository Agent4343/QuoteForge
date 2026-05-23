import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useLogin } from "../api/hooks";
import { ApiError } from "../api/client";
import { Field, Spinner } from "../components/ui";
import { useAuth } from "../stores/auth";

const schema = z.object({ email: z.string().email(), password: z.string().min(1) });
type Form = z.infer<typeof schema>;

export default function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setTokens = useAuth((s) => s.setTokens);
  const login = useLogin();
  const [error, setError] = useState("");
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) });

  const onSubmit = (data: Form) => {
    setError("");
    login.mutate(data, {
      onSuccess: (tokens) => {
        setTokens(tokens);
        navigate("/dashboard");
      },
      onError: (e) => setError(e instanceof ApiError ? String(e.detail) : t("common.error")),
    });
  };

  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <h1 className="mb-1 text-2xl font-bold text-brand">{t("app.name")}</h1>
      <p className="mb-6 text-sm text-gray-500">{t("app.tagline")}</p>
      <form onSubmit={handleSubmit(onSubmit)} className="card">
        <h2 className="mb-4 text-lg font-semibold">{t("auth.login")}</h2>
        {error && <p className="field-error mb-3">{error}</p>}
        <Field label={t("auth.email")} error={formState.errors.email?.message}>
          <input className="input" type="email" inputMode="email" autoComplete="email" {...register("email")} />
        </Field>
        <Field label={t("auth.password")} error={formState.errors.password?.message}>
          <input className="input" type="password" autoComplete="current-password" {...register("password")} />
        </Field>
        <button className="btn-primary w-full mt-2" disabled={login.isPending}>
          {login.isPending ? <Spinner /> : t("auth.login")}
        </button>
        <div className="mt-4 flex justify-between text-sm">
          <Link className="text-brand" to="/register">{t("auth.register")}</Link>
          <Link className="text-gray-500" to="/forgot-password">{t("auth.forgot")}</Link>
        </div>
      </form>
    </div>
  );
}
