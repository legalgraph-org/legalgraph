import { existsSync } from "node:fs";
import { join } from "node:path";

import { SOURCE_LOCALE, type SupportedLocale } from "./locales";
import { readPo, usableTranslations } from "./po";

/** locales/ at the project root; `astro build` and the scripts run from there. */
export const LOCALES_DIR = join(process.cwd(), "locales");

const cache = new Map<SupportedLocale, ReadonlyMap<string, string>>();

/**
 * The usable translations of one locale, parsed once per build. The source locale has none: its
 * msgids are the text.
 */
export function loadCatalog(locale: SupportedLocale): ReadonlyMap<string, string> {
  const cached = cache.get(locale);
  if (cached) {
    return cached;
  }
  let catalog: ReadonlyMap<string, string> = new Map();
  if (locale !== SOURCE_LOCALE) {
    const path = join(LOCALES_DIR, `${locale}.po`);
    if (!existsSync(path)) {
      throw new Error(`Missing catalog ${path}: run make i18n-extract`);
    }
    catalog = usableTranslations(readPo(path));
  }
  cache.set(locale, catalog);
  return catalog;
}
