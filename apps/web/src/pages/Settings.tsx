import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useMe, useUpdateMe } from "../api/hooks";
import { PROVINCES } from "../api/types";
import type { UserUpdate } from "../api/types";
import { setLanguage } from "../i18n";
import { Field, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../stores/auth";

export default function Settings() {
  const { t } = useTranslation();
  const token = useAuth((s) => s.accessToken);
  const me = useMe(!!token);
  const update = useUpdateMe();
  const { register, handleSubmit, reset } = useForm<UserUpdate>();

  useEffect(() => {
    if (me.data) reset(me.data);
  }, [me.data, reset]);

  if (me.isLoading || !me.data) return <Spinner label={t("common.loading")} />;

  const onSubmit = (data: UserUpdate) => {
    update.mutate(data, {
      onSuccess: (u) => {
        if (u.language) setLanguage(u.language);
      },
    });
  };

  return (
    <div className="max-w-2xl">
      <PageHeader title={t("settings.title")} />
      <form onSubmit={handleSubmit(onSubmit)} className="grid gap-5">
        <section className="card">
          <h2 className="mb-3 font-semibold">{t("settings.profile")}</h2>
          <Field label={t("auth.fullName")}><input className="input" {...register("full_name")} /></Field>
          <Field label={t("auth.businessName")}><input className="input" {...register("business_name")} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("auth.province")}>
              <select className="input" {...register("province")}>
                {PROVINCES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label={t("settings.language")}>
              <select className="input" {...register("language")}>
                <option value="en">English</option>
                <option value="fr">Français</option>
              </select>
            </Field>
          </div>
          <Field label={t("settings.esa")}><input className="input" {...register("esa_license_number")} /></Field>
          <Field label={t("settings.rbq")}><input className="input" {...register("rbq_license_number")} /></Field>
          <Field label={t("settings.cmeq")}><input className="input" {...register("cmeq_membership_number")} /></Field>
          <Field label={t("settings.logoUrl")}><input className="input" {...register("logo_url")} /></Field>
          <Field label={t("settings.color")}><input className="input" type="text" {...register("primary_color_hex")} placeholder="#1a3e5c" /></Field>
        </section>

        <section className="card" id="labor-rates">
          <h2 className="mb-3 font-semibold">{t("settings.laborRates")}</h2>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("settings.blendedRate")}>
              <input className="input" inputMode="decimal" {...register("blended_labor_rate_cad")} />
            </Field>
            <Field label={t("settings.apprenticeRate")}>
              <input className="input" inputMode="decimal" {...register("apprentice_labor_rate_cad")} />
            </Field>
          </div>
          <Field label={t("settings.minCallout")}>
            <input className="input" inputMode="decimal" {...register("minimum_callout_hours")} />
          </Field>
        </section>

        <section className="card" id="markup">
          <h2 className="mb-3 font-semibold">{t("settings.markup")}</h2>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("settings.materialMarkup")}>
              <input className="input" inputMode="decimal" {...register("default_material_markup_pct")} />
            </Field>
            <Field label={t("settings.labourMarkup")}>
              <input className="input" inputMode="decimal" {...register("default_labor_markup_pct")} />
            </Field>
          </div>
          <Field label={t("settings.minMargin")}>
            <input className="input" inputMode="decimal" {...register("minimum_margin_pct")} />
          </Field>
        </section>

        <div>
          <button className="btn-primary" disabled={update.isPending}>
            {update.isPending ? t("common.saving") : t("settings.save")}
          </button>
          {update.isSuccess && <span className="ml-3 text-sm text-green-700">{t("settings.saved")}</span>}
        </div>
      </form>
    </div>
  );
}
