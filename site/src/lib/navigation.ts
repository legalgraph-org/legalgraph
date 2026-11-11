import type { FooterColumn } from "../components/ds/footer.types";
import type { LanguageOption } from "../components/ds/language-switcher.types";
import type { NavItem, NavMenuEntry } from "../components/ds/navbar.types";
import { LOCALE_FLAGS, LOCALE_NAMES, LOCALE_TAGS, SUPPORTED_LOCALES } from "../i18n/locales";
import type { Translate } from "../i18n/t";
import { pagePath, type PageId } from "./routes";

/**
 * The site's navigation: the navbar's menus, the footer's columns and the language dialog. Labels
 * are translated; links to the prose pages go to the same language, links to the data pages to
 * the one version there is. `path` is the page being shown, to mark the current entry.
 */
type Entry = NavMenuEntry & { href: string };

/** The project's repository: the data, the law texts, the code and the tests. */
export const GITHUB_URL = "https://github.com/legalgraph-org/legalgraph";

function explore(t: Translate): Entry[] {
  return [
    { label: t("Checklist"), href: pagePath("checklist", t.locale), icon: "✓", description: t("Answer a few questions, see which rules apply") },
    { label: t("Countries"), href: pagePath("countries", t.locale), icon: "◎", description: t("Jurisdictions, their laws and provisions") },
    { label: t("Laws"), href: pagePath("acts", t.locale), icon: "⚖", description: t("Laws, judgments and guidelines, by country") },
    { label: t("Provisions"), href: pagePath("provisions", t.locale), icon: "≡", description: t("Every provision, with its quote and its English") },
    { label: t("Rules"), href: pagePath("rules", t.locale), icon: "§", description: t("Obligations, the conditions they apply under") },
    { label: t("Compare"), href: pagePath("items", t.locale), icon: "▦", description: t("Which information each country's law requires") },
    { label: t("Graph"), href: pagePath("graph", t.locale), icon: "⌘", description: t("Click through laws, provisions and concepts") },
  ];
}

function data(t: Translate): Entry[] {
  return [
    { label: t("Law texts"), href: pagePath("sources", t.locale), icon: "¶", description: t("The official originals, their hashes and annotations") },
    { label: t("Method"), href: pagePath("method", t.locale), icon: "↻", description: t("How the text is fetched, checked and turned into data") },
    { label: t("Downloads"), href: pagePath("download", t.locale), icon: "↓", description: t("Turtle, N-Triples, JSON-LD and the ontology") },
    { label: t("Glossary"), href: pagePath("glossary", t.locale), icon: "Aa", description: t("The abbreviations on this site, explained") },
  ];
}

/** Products others build on the graph, and the article on how; the products live on their own sites. */
function solutions(t: Translate): Entry[] {
  const aimix = `https://aimix.io/${t.locale === "de" ? "de" : "en"}`;
  return [
    { label: t("Impressum template generator"), href: `${aimix}/impressum-template-generator`, icon: "✎", description: t("By Aimix: your imprint as a template, built on this graph") },
    { label: t("Built on legalgraph"), href: pagePath(`blog/${BUILT_ON_SLUG}`, t.locale), icon: "→", description: t("A guest article: from the dataset to a product") },
  ];
}

/** The guest article the Solutions menu points to. */
const BUILT_ON_SLUG = "built-on-legalgraph-impressum-generator";

function isCurrent(href: string, path: string): boolean {
  const target = href.split("#")[0]!;
  return target === "/" ? path === "/" : path === target || path.startsWith(`${target}/`);
}

export function navItems(t: Translate, path: string): NavItem[] {
  const menu = (label: string, entries: Entry[]): NavItem => {
    const marked = entries.map((entry) => ({ ...entry, current: isCurrent(entry.href, path) }));
    return { kind: "menu", label, current: marked.some((e) => e.current), groups: [{ entries: marked }] };
  };
  const link = (label: string, page: PageId): NavItem => {
    const href = pagePath(page, t.locale);
    return { kind: "link", label, href, current: isCurrent(href, path) };
  };
  return [
    menu(t("Explore"), explore(t)),
    menu(t("Data"), data(t)),
    menu(t("Solutions"), solutions(t)),
    link(t("Articles"), "blog"),
    link(t("About"), "about"),
  ];
}

export function footerColumns(t: Translate): FooterColumn[] {
  const page = (label: string, id: PageId) => ({ label, href: pagePath(id, t.locale) });
  return [
    { title: t("Explore"), links: explore(t).map(({ label, href }) => ({ label, href })) },
    { title: t("Data"), links: data(t).map(({ label, href }) => ({ label, href })) },
    {
      title: t("Project"),
      links: [
        page(t("About"), "about"),
        page(t("Articles"), "blog"),
        { label: "GitHub", href: GITHUB_URL },
        { label: "Aimix", href: "https://aimix.io" },
      ],
    },
    {
      title: t("Legal"),
      links: [page(t("Imprint"), "legal/imprint"), page(t("Privacy"), "legal/privacy"), page(t("Terms of use"), "legal/terms")],
    },
  ];
}

export const LANGUAGE_DIALOG_ID = "language-dialog";

/**
 * The language dialog's links: the same page in every language. A data page exists in one
 * version only, so its options lead to each language's home instead.
 */
export function languageOptions(t: Translate, page: PageId | undefined): LanguageOption[] {
  return SUPPORTED_LOCALES.map((locale) => ({
    code: LOCALE_TAGS[locale].split("-")[0] ?? locale,
    name: LOCALE_NAMES[locale],
    flag: LOCALE_FLAGS[locale],
    href: pagePath(page ?? "home", locale),
    current: page !== undefined && locale === t.locale,
  }));
}
