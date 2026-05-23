import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useCustomers } from "../api/hooks";
import { PageHeader, Spinner } from "../components/ui";

export default function Customers() {
  const { t } = useTranslation();
  const { data, isLoading } = useCustomers();

  return (
    <div>
      <PageHeader
        title={t("customers.title")}
        action={<Link to="/customers/new" className="btn-primary">{t("customers.new")}</Link>}
      />
      {isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : data && data.length > 0 ? (
        <div className="grid gap-3">
          {data.map((c) => (
            <Link key={c.id} to={`/customers/${c.id}`} className="card hover:border-brand">
              <div className="font-semibold">{c.name}</div>
              <div className="text-sm text-gray-500">
                {c.company ? `${c.company} · ` : ""}{c.city}, {c.province}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-gray-500">{t("customers.empty")}</p>
      )}
    </div>
  );
}
