import { getCollection, getEntry, type CollectionEntry } from "astro:content";
import { formatDate as formatLocaleDate } from "../i18n/format";
import { SOURCE_LOCALE, SUPPORTED_LOCALES, type SupportedLocale } from "../i18n/locales";

/**
 * Markdown content in every language: <name>.md is English, <name>.<locale>.md its translation.
 * A page whose translation is missing shows the English text (and says so).
 */
const LOCALE_SUFFIX = new RegExp(`\\.(${SUPPORTED_LOCALES.join("|")})$`);

export const baseName = (id: string) => id.replace(LOCALE_SUFFIX, "");
const isTranslation = (id: string) => LOCALE_SUFFIX.test(id);

export interface Localized<E> {
  /** The URL name: the file name without the locale. */
  slug: string;
  entry: E;
  /** False when the English text stands in for a missing translation. */
  translated: boolean;
}

async function localized<C extends "blog" | "legal">(
  collection: C,
  slug: string,
  locale: SupportedLocale,
): Promise<Localized<CollectionEntry<C>>> {
  const own = locale === SOURCE_LOCALE ? undefined : await getEntry(collection, `${slug}.${locale}`);
  const english = await getEntry(collection, slug);
  const entry = (own ?? english) as CollectionEntry<C> | undefined;
  if (!entry) {
    throw new Error(`src/content/${collection}/${slug}.md is missing`);
  }
  return { slug, entry, translated: locale === SOURCE_LOCALE || own !== undefined };
}

/** Published articles in a language, newest first. Drafts are visible in `astro dev` only. */
export async function articles(locale: SupportedLocale): Promise<Localized<CollectionEntry<"blog">>[]> {
  const english = await getCollection("blog", (entry) => !isTranslation(entry.id) && (import.meta.env.DEV || !entry.data.draft));
  const posts = await Promise.all(english.map((entry) => localized("blog", entry.id, locale)));
  return posts.sort((a, b) => b.entry.data.published.getTime() - a.entry.data.published.getTime());
}

export const LEGAL_PAGES = ["imprint", "privacy", "terms"] as const;
export type LegalPage = (typeof LEGAL_PAGES)[number];

export const legalPage = (slug: LegalPage, locale: SupportedLocale) => localized("legal", slug, locale);

export const formatDate = (locale: SupportedLocale, date: Date) => formatLocaleDate(locale, date);

/** Minutes to read an article, at 200 words a minute; at least one. */
export const readingMinutes = (entry: CollectionEntry<"blog">) =>
  Math.max(1, Math.round((entry.body ?? "").split(/\s+/).filter(Boolean).length / 200));
