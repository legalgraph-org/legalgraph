import type { SupportedLocale } from "../i18n/locales";
import { pagePath } from "./routes";

/**
 * The glossary's tooltips on the site's own pages: the first use of each
 * abbreviation on a page gets a dashed underline, a tooltip on hover and keyboard focus (CSS only,
 * styles/patterns.css), and a link to its entry on /glossary. Pages written as messages and Markdown
 * cannot wrap terms by hand, so markAbbreviations() does it on the rendered HTML (Article.astro).
 * No Astro APIs here, so it can be tested; lib/glossary.ts loads the entries.
 */
export interface GlossaryEntry {
  id: string;
  /** As the abbreviation is written in this language, e.g. "DSGVO" for the GDPR in German. */
  term: string;
  kind: "law" | "body" | "business" | "standard" | "licence" | "service";
  graph?: string;
  source?: { label: string; url: string };
  original?: { text: string; lang: string };
  seeAlso: string[];
  match: string[];
  expansion: string;
  short: string;
  body: string[];
}

export const glossaryHref = (id: string, locale: SupportedLocale) => `${pagePath("glossary", locale)}#${id}`;

/** What the letters stand for in their own language, where the page is in another one. */
export function originalLine(entry: GlossaryEntry, locale: SupportedLocale) {
  const { original } = entry;
  if (!original || original.lang === locale || original.text === entry.expansion) return undefined;
  const language = new Intl.DisplayNames([locale], { type: "language" }).of(original.lang) ?? original.lang;
  return { ...original, language };
}

// Inside these, a term is left alone: it is already a link, code, a heading or a figure.
const SKIP = new Set(["a", "abbr", "button", "code", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "label", "pre", "script", "style", "svg", "textarea", "title"]);
const escape = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const pattern = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

let tooltips = 0;

/**
 * The tooltip link for one use of a term: the abbreviation, and a tooltip
 * with what it stands for, its original wording where the page's language differs, and one sentence.
 */
export function abbreviationHtml(entry: GlossaryEntry, text: string, locale: SupportedLocale): string {
  tooltips += 1;
  const id = `abbr-${entry.id}-${tooltips}`;
  const original = originalLine(entry, locale);
  return (
    `<a href="${glossaryHref(entry.id, locale)}" class="glossary-abbr" aria-describedby="${id}">` +
    `<abbr>${escape(text)}</abbr>` +
    `<span id="${id}" role="tooltip" class="glossary-tip">` +
    `<span class="glossary-tip-title">${escape(entry.expansion)}</span>` +
    (original
      ? `<span class="glossary-tip-original">${escape(original.language)}: <i lang="${escape(original.lang)}">${escape(original.text)}</i></span>`
      : "") +
    `<span class="glossary-tip-short">${escape(entry.short)}</span>` +
    `</span></a>`
  );
}

/**
 * Marks the first use of each glossary term in a page's rendered HTML. Only text is touched, never
 * tags or attributes, and nothing inside links, code, headings or figures. A term is a whole word:
 * "EU" is not marked inside "EUR-Lex", but is before a hyphen ("EU-US"). The longest spelling wins,
 * so "JSON-LD" is not read as "JSON".
 */
export function markAbbreviations(html: string, entries: readonly GlossaryEntry[], locale: SupportedLocale): string {
  const bySpelling = new Map<string, GlossaryEntry>();
  for (const entry of entries) for (const spelling of entry.match) bySpelling.set(spelling, entry);
  if (bySpelling.size === 0) return html;
  const spellings = [...bySpelling.keys()].sort((a, b) => b.length - a.length).map(pattern);
  const word = new RegExp(`(?<![\\p{L}\\p{N}_/@.-])(${spellings.join("|")})(?![\\p{L}\\p{N}_/@])`, "gu");
  const used = new Set<string>();
  let skipping = 0;
  return html
    .split(/(<[^>]+>)/)
    .map((part) => {
      if (part.startsWith("<")) {
        const tag = /^<(\/?)([a-zA-Z][a-zA-Z0-9-]*)/.exec(part);
        if (tag && SKIP.has(tag[2]!.toLowerCase()) && !part.endsWith("/>")) skipping += tag[1] ? -1 : 1;
        return part;
      }
      if (skipping > 0) return part;
      return part.replace(word, (text: string) => {
        const entry = bySpelling.get(text)!;
        if (used.has(entry.id)) return text;
        used.add(entry.id);
        return abbreviationHtml(entry, text, locale);
      });
    })
    .join("");
}
