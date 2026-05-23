import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { useCreateCustomer } from "../api/hooks";
import { PROVINCES } from "../api/types";
import { Field, PageHeader, Spinner } from "../components/ui";

const schema = z.object({
  name: z.string().min(1),
  company: z.string().optional(),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().optional(),
  address_line1: z.string().min(1),
  address_line2: z.string().optional(),
  city: z.string().min(1),
  province: z.enum(["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"]),
  postal_code: z.string().min(1),
  notes: z.string().optional(),
});
type Form = z.infer<typeof schema>;

export default function CustomerForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const create = useCreateCustomer();
  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { province: "ON" },
  });

  const onSubmit = (data: Form) => {
    const payload = { ...data, email: data.email || undefined };
    create.mutate(payload, { onSuccess: () => navigate("/customers") });
  };

  return (
    <div className="max-w-xl">
      <PageHeader title={t("customers.new")} />
      <form onSubmit={handleSubmit(onSubmit)} className="card">
        <Field label={t("customers.name")} error={formState.errors.name?.message}>
          <input className="input" {...register("name")} />
        </Field>
        <Field label={t("customers.company")}><input className="input" {...register("company")} /></Field>
        <Field label={t("auth.email")} error={formState.errors.email?.message}>
          <input className="input" type="email" inputMode="email" {...register("email")} />
        </Field>
        <Field label={t("customers.phone")}>
          <input className="input" type="tel" inputMode="tel" {...register("phone")} />
        </Field>
        <Field label={t("customers.address1")} error={formState.errors.address_line1?.message}>
          <input className="input" {...register("address_line1")} />
        </Field>
        <Field label={t("customers.address2")}><input className="input" {...register("address_line2")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("customers.city")} error={formState.errors.city?.message}>
            <input className="input" {...register("city")} />
          </Field>
          <Field label={t("auth.province")}>
            <select className="input" {...register("province")}>
              {PROVINCES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
        </div>
        <Field label={t("customers.postal")} error={formState.errors.postal_code?.message}>
          <input className="input" {...register("postal_code")} />
        </Field>
        <Field label={t("customers.notes")}><textarea className="input min-h-[80px] py-2" {...register("notes")} /></Field>
        <button className="btn-primary w-full" disabled={create.isPending}>
          {create.isPending ? <Spinner /> : t("customers.save")}
        </button>
      </form>
    </div>
  );
}
