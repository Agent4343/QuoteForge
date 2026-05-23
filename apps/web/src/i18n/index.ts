import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import fr from "./fr.json";

const stored = localStorage.getItem("qf_lang");

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fr: { translation: fr } },
  lng: stored || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLanguage(lang: "en" | "fr") {
  localStorage.setItem("qf_lang", lang);
  void i18n.changeLanguage(lang);
}

export default i18n;
