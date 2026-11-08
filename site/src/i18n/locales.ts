/** English, and German for the German-speaking countries. Add a locale here and run make i18n-extract. */
export const SUPPORTED_LOCALES = ["en", "de"] as const;

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

/** The source language: its msgids are the English text, so it has no .po file. */
export const SOURCE_LOCALE: SupportedLocale = "en";

/** Locales with a translated catalog in locales/<locale>.po. */
export const TRANSLATED_LOCALES: readonly SupportedLocale[] = SUPPORTED_LOCALES.filter(
  (locale) => locale !== SOURCE_LOCALE,
);

/** OpenGraph locales (og:locale). */
export const OG_LOCALES: Readonly<Record<SupportedLocale, string>> = {
  en: "en_US",
  de: "de_DE",
};

/** Flags shown next to the language names. */
export const LOCALE_FLAGS: Readonly<Record<SupportedLocale, string>> = {
  en: "🇬🇧",
  de: "🇩🇪",
};

export const LOCALE_NAMES: Readonly<Record<SupportedLocale, string>> = {
  en: "English",
  de: "Deutsch",
};

/** BCP 47 tags for Intl formatting and <html lang>. */
export const LOCALE_TAGS: Readonly<Record<SupportedLocale, string>> = {
  en: "en-GB",
  de: "de-DE",
};

export function isSupportedLocale(value: string): value is SupportedLocale {
  return SUPPORTED_LOCALES.some((locale) => locale === value);
}

/**
 * Narrows a route's locale (`Astro.params.locale`, `Astro.currentLocale`: `string | undefined`)
 * to a supported locale. Throws, so a misconfigured route fails the build instead of quietly
 * rendering English.
 */
export function requireLocale(value: string | undefined): SupportedLocale {
  if (value === undefined || !isSupportedLocale(value)) {
    throw new Error(
      `Unsupported locale ${JSON.stringify(value)}; expected one of ${SUPPORTED_LOCALES.join(", ")}`,
    );
  }
  return value;
}
