import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useCustomer, useDeleteCustomer, useUpdateCustomer } from "../api/hooks";
import { PROVINCES } from "../api/types";
import type { CustomerUpdate } from "../api/types";
import { Field, PageHeader, Spinner } from "../components/ui";

export default function CustomerDetail() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading } = useCustomer(id);
  const update = useUpdateCustomer(id);
  const del = useDeleteCustomer();
  const { register, handleSubmit, reset } = useForm<CustomerUpdate>();

  useEffect(() => {
    if (data) reset(data);
  }, [data, reset]);

  if (isLoading || !data) return <Spinner label={t("common.loading")} />;

  return (
    <div className="max-w-xl">
      <PageHeader
        title={data.name}
        action={
          <button
            className="btn-danger"
            onClick={() => {
              if (confirm(t("customers.confirmDelete")))
                del.mutate(id, { onSuccess: () => navigate("/customers") });
            }}
          >
            {t("customers.delete")}
          </button>
        }
      />
      <form onSubmit={handleSubmit((d) => update.mutate(d))} className="card">
        <Field label={t("customers.name")}><input className="input" {...register("name")} /></Field>
        <Field label={t("customers.company")}><input className="input" {...register("company")} /></Field>
        <Field label={t("auth.email")}><input className="input" type="email" {...register("email")} /></Field>
        <Field label={t("customers.phone")}><input className="input" type="tel" {...register("phone")} /></Field>
        <Field label={t("customers.address1")}><input className="input" {...register("address_line1")} /></Field>
        <Field label={t("customers.address2")}><input className="input" {...register("address_line2")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("customers.city")}><input className="input" {...register("city")} /></Field>
          <Field label={t("auth.province")}>
            <select className="input" {...register("province")}>
              {PROVINCES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
        </div>
        <Field label={t("customers.postal")}><input className="input" {...register("postal_code")} /></Field>
        <Field label={t("customers.notes")}><textarea className="input min-h-[80px] py-2" {...register("notes")} /></Field>
        <button className="btn-primary w-full" disabled={update.isPending}>
          {update.isPending ? <Spinner /> : t("customers.save")}
        </button>
        {update.isSuccess && <p className="mt-2 text-sm text-green-700">{t("settings.saved")}</p>}
      </form>
    </div>
  );
}
