import { SOURCE_LOCALE, SUPPORTED_LOCALES, type SupportedLocale } from "../i18n/locales";

/**
 * The pages that exist in every language: the prose of the site (home, about, articles, legal), the
 * Data menu (law texts, method, downloads, glossary) and the Explore menu (checklist, countries,
 * laws, provisions, rules, compare, graph). Each language has its prefix, English included: /en,
 * /en/about, /de, /de/about … The graph's own resources (/id/…, /vocab/…) exist once, unprefixed:
 * their addresses are the identifiers the data publishes.
 */
export const PAGES = [
  "home",
  "about",
  "blog",
  "sources",
  "method",
  "download",
  "glossary",
  "checklist",
  "countries",
  "acts",
  "provisions",
  "rules",
  "items",
  "graph",
  "legal/imprint",
  "legal/privacy",
  "legal/terms",
] as const;

export type StaticPage = (typeof PAGES)[number];
export type PageId = StaticPage | `blog/${string}`;

export function pagePath(page: PageId, locale: SupportedLocale): string {
  return page === "home" ? `/${locale}` : `/${locale}/${page}`;
}

/**
 * Where the old, unprefixed English addresses (/, /method, /blog/<slug> …) go now: their /en page.
 * astro.config.mjs turns these into redirects, for the dev server and as permanent (301) redirects
 * where the site is served (_redirects).
 */
export function unprefixedRedirects(blogSlugs: readonly string[]): Record<string, string> {
  const pages: PageId[] = [...PAGES, ...blogSlugs.map((slug) => `blog/${slug}` as const)];
  return Object.fromEntries(pages.map((page) => [page === "home" ? "/" : `/${page}`, pagePath(page, SOURCE_LOCALE)]));
}

export interface Alternate {
  hreflang: string;
  href: string;
}

/** hreflang links for a page: one per language plus x-default (the English page). */
export function alternatesFor(page: PageId, site: URL): Alternate[] {
  const absolute = (path: string) => new URL(path, site).href;
  return [
    ...SUPPORTED_LOCALES.map((locale) => ({ hreflang: locale, href: absolute(pagePath(page, locale)) })),
    { hreflang: "x-default", href: absolute(pagePath(page, SOURCE_LOCALE)) },
  ];
}

/** The language of a page by its path (/de/countries → de); the graph's own pages are English. */
export function localeOfPath(pathname: string): SupportedLocale {
  const first = pathname.split("/")[1] ?? "";
  return (SUPPORTED_LOCALES as readonly string[]).includes(first) ? (first as SupportedLocale) : SOURCE_LOCALE;
}
