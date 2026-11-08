import { readFileSync, writeFileSync } from "node:fs";

import type { SupportedLocale } from "../../src/i18n/locales";

/**
 * gettext Plural-Forms per locale: the source of truth for plural selection.
 * English and German have two forms.
 */
export const PLURAL_FORMS: Readonly<Record<SupportedLocale, string>> = {
  en: "nplurals=2; plural=(n != 1);",
  de: "nplurals=2; plural=(n != 1);",
};

/** Sets Language and Plural-Forms in the header entry, keeping msgmerge's layout. */
export function ensureHeaders(poPath: string, locale: SupportedLocale): void {
  const source = readFileSync(poPath, "utf8");
  const headerEnd = source.indexOf("\n\n");
  const header = headerEnd === -1 ? source : source.slice(0, headerEnd);
  const rest = headerEnd === -1 ? "" : source.slice(headerEnd);
  const wanted: Record<string, string> = { Language: locale, "Plural-Forms": PLURAL_FORMS[locale] };
  let updated = header;
  for (const [name, value] of Object.entries(wanted)) {
    const line = `"${name}: ${value}\\n"`;
    const existing = new RegExp(`^"${name}:.*"$`, "m");
    updated = existing.test(updated) ? updated.replace(existing, line) : `${updated}\n${line}`;
  }
  writeFileSync(poPath, `${updated}${rest}`);
}
