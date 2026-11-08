import { loadCatalog } from "./catalog";
import { requireLocale, SOURCE_LOCALE, type SupportedLocale } from "./locales";
import { interpolate, messageKey, normalizeMsgid, type MessageValues } from "./message";

export interface Translate {
  /** gettext-style: the English text is the key. Arguments must be string literals (extractor). */
  (msgid: string, values?: MessageValues): string;
  /** msgctxt, for identical English text with different meanings. */
  ctx(context: string, msgid: string, values?: MessageValues): string;
  readonly locale: SupportedLocale;
}

const reportedMissing = new Set<string>();

function reportMissing(locale: SupportedLocale, key: string): void {
  const id = `${locale}:${key}`;
  if (!reportedMissing.has(id)) {
    reportedMissing.add(id);
    console.warn(
      `[i18n] ${locale}: missing or fuzzy translation, using English: ${JSON.stringify(key)}`,
    );
  }
}

export function translator(
  locale: SupportedLocale,
  catalog: ReadonlyMap<string, string>,
): Translate {
  const lookup = (
    msgid: string,
    context: string | undefined,
    values: MessageValues | undefined,
  ) => {
    const key = messageKey(msgid, context);
    const translated = catalog.get(key);
    if (translated === undefined && locale !== SOURCE_LOCALE) {
      reportMissing(locale, key);
    }
    return interpolate(translated ?? normalizeMsgid(msgid), values);
  };
  const t = (msgid: string, values?: MessageValues) => lookup(msgid, undefined, values);
  return Object.assign(t, {
    ctx: (context: string, msgid: string, values?: MessageValues) => lookup(msgid, context, values),
    locale,
  });
}

/**
 * The translate function for a page: `const t = useT(Astro.params.locale)`. Runs at build time
 * only; nothing of it reaches the browser.
 */
export function useT(locale: string | undefined): Translate {
  const supported = requireLocale(locale);
  return translator(supported, loadCatalog(supported));
}
