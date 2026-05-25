import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useMe } from "../api/hooks";
import { setLanguage } from "../i18n";
import { useAuth } from "../stores/auth";

function LanguageToggle() {
  const { i18n } = useTranslation();
  return (
    <div className="flex rounded-lg border border-gray-300 overflow-hidden text-sm">
      {(["en", "fr"] as const).map((l) => (
        <button
          key={l}
          onClick={() => setLanguage(l)}
          className={`px-3 py-1 ${i18n.language === l ? "bg-brand text-white" : "bg-white text-gray-600"}`}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export default function Layout() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accessToken, setUser, logout } = useAuth();
  const me = useMe(!!accessToken);

  useEffect(() => {
    if (me.data) setUser(me.data);
  }, [me.data, setUser]);

  const links = [
    { to: "/dashboard", label: t("nav.dashboard") },
    { to: "/quotes", label: t("nav.quotes") },
    { to: "/customers", label: t("nav.customers") },
    { to: "/code-reference", label: t("nav.codeRef") },
    { to: "/settings", label: t("nav.settings") },
  ];

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
          <span className="text-lg font-bold text-brand">{t("app.name")}</span>
          <nav className="flex flex-1 flex-wrap gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive ? "bg-brand-50 text-brand" : "text-gray-600 hover:bg-gray-100"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <LanguageToggle />
          <button
            className="text-sm text-gray-500 hover:text-gray-800"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            {t("nav.logout")}
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
