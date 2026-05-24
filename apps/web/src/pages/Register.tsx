import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useRegister } from "../api/hooks";
import { PROVINCES } from "../api/types";
import { Field, Spinner } from "../components/ui";
import { errorMessage } from "../lib/errors";
import { useAuth } from "../stores/auth";

const schema = z.object({
  full_name: z.string().min(1, "Your name is required"),
  business_name: z.string().min(1, "Business name is required"),
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(10, "Password must be at least 10 characters"),
  province: z.enum(["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"]),
});
type Form = z.infer<typeof schema>;

export default function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setTokens = useAuth((s) => s.setTokens);
  const reg = useRegister();
  const [error, setError] = useState("");
  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: { province: "ON" },
  });

  const onSubmit = (data: Form) => {
    setError("");
    reg.mutate(data, {
      onSuccess: (tokens) => {
        setTokens(tokens);
        navigate("/settings");
      },
      onError: (e) => setError(errorMessage(e)),
    });
  };

  return (
    <div className="mx-auto mt-12 max-w-sm px-4">
      <h1 className="mb-6 text-2xl font-bold text-brand">{t("app.name")}</h1>
      <form
        onSubmit={handleSubmit(onSubmit, () => setError("Please fix the highlighted fields below."))}
        className="card"
        noValidate
      >
        <h2 className="mb-4 text-lg font-semibold">{t("auth.register")}</h2>
        {error && (
          <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}
        <Field label={t("auth.fullName")} error={formState.errors.full_name?.message}>
          <input className="input" {...register("full_name")} />
        </Field>
        <Field label={t("auth.businessName")} error={formState.errors.business_name?.message}>
          <input className="input" {...register("business_name")} />
        </Field>
        <Field label={t("auth.province")} error={formState.errors.province?.message}>
          <select className="input" {...register("province")}>
            {PROVINCES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </Field>
        <Field label={t("auth.email")} error={formState.errors.email?.message}>
          <input className="input" type="email" inputMode="email" {...register("email")} />
        </Field>
        <Field label={t("auth.password")} error={formState.errors.password?.message}>
          <input className="input" type="password" autoComplete="new-password" {...register("password")} />
          <p className="mt-1 text-xs text-gray-500">At least 10 characters.</p>
        </Field>
        <button className="btn-primary w-full mt-2" disabled={reg.isPending}>
          {reg.isPending ? <Spinner /> : t("auth.register")}
        </button>
        <div className="mt-4 text-sm">
          <Link className="text-brand" to="/login">{t("auth.haveAccount")}</Link>
        </div>
      </form>
    </div>
  );
}
