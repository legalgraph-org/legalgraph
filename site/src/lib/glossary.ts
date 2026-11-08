import { getCollection } from "astro:content";

import type { SupportedLocale } from "../i18n/locales";
import { markAbbreviations, type GlossaryEntry } from "./glossary-markup";

export { glossaryHref, originalLine, type GlossaryEntry } from "./glossary-markup";

/** The glossary (src/content/glossary.yaml), by language, sorted by term; its cross-references checked. */
let loaded: Promise<Map<SupportedLocale, GlossaryEntry[]>> | undefined;

async function load(): Promise<Map<SupportedLocale, GlossaryEntry[]>> {
  const all = await getCollection("glossary");
  const ids = new Set(all.map((entry) => entry.id));
  for (const entry of all) {
    const unknown = entry.data.seeAlso.filter((id) => !ids.has(id));
    if (unknown.length) throw new Error(`glossary.yaml: ${entry.id} sees also unknown ${unknown.join(", ")}`);
  }
  const byLocale = new Map<SupportedLocale, GlossaryEntry[]>();
  for (const locale of ["en", "de"] as const) {
    const entries = all.map(({ id, data }) => {
      const text = data[locale];
      return {
        id,
        term: text.match[0] ?? data.en.match[0] ?? id,
        kind: data.kind,
        graph: data.graph,
        source: data.source,
        original: data.original,
        seeAlso: data.seeAlso,
        match: text.match,
        expansion: text.expansion,
        short: text.short,
        body: text.body.trim().split(/\n\s*\n/),
      };
    });
    entries.sort((a, b) => a.term.localeCompare(b.term, locale, { sensitivity: "base" }));
    byLocale.set(locale, entries);
  }
  return byLocale;
}

export async function glossary(locale: SupportedLocale): Promise<GlossaryEntry[]> {
  loaded ??= load();
  return (await loaded).get(locale) ?? [];
}

/** A page's marker: markAbbreviations with this language's glossary. */
export async function abbreviationMarker(locale: SupportedLocale): Promise<(html: string) => string> {
  const entries = await glossary(locale);
  return (html) => markAbbreviations(html, entries, locale);
}
