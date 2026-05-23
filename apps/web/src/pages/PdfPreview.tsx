import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ApiError, fetchPdf } from "../api/client";
import { PageHeader, Spinner } from "../components/ui";

export default function PdfPreview() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let revoke: string | null = null;
    fetchPdf(`/api/quotes/${id}/pdf`)
      .then((u) => {
        revoke = u;
        setUrl(u);
      })
      .catch((e) => setError(e instanceof ApiError ? String(e.detail) : t("common.error")));
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [id, t]);

  return (
    <div>
      <PageHeader
        title={t("quotes.preview")}
        action={<Link to={`/quotes/${id}`} className="btn-secondary">{t("common.back")}</Link>}
      />
      {error ? (
        <p className="field-error">{error}</p>
      ) : url ? (
        <>
          <a className="btn-primary mb-3 inline-flex" href={url} download={`quote-${id}.pdf`}>
            {t("quotes.downloadPdf")}
          </a>
          <iframe title="pdf" src={url} className="h-[80vh] w-full rounded-lg border border-gray-200" />
        </>
      ) : (
        <Spinner label={t("common.loading")} />
      )}
    </div>
  );
}
