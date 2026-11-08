import type { SupportedLocale } from "../../src/i18n/locales";
import { messageKey, placeholdersOf, tagsOf } from "../../src/i18n/message";
import type { PoEntry, PoFile } from "../../src/i18n/po";

export interface CheckProblem {
  locale: SupportedLocale | "pot";
  msgid?: string;
  message: string;
}

const sameList = (a: readonly (string | number)[], b: readonly (string | number)[]) =>
  a.length === b.length && a.every((value, index) => value === b[index]);

const keyOf = (entry: Pick<PoEntry, "msgid" | "context">) => messageKey(entry.msgid, entry.context);

/** The pot must hold exactly what the sources use (otherwise make i18n-extract was not run). */
export function checkTemplate(pot: PoFile, extractedKeys: ReadonlySet<string>): CheckProblem[] {
  const potKeys = new Set(pot.entries.map(keyOf));
  const problems: CheckProblem[] = [];
  for (const key of extractedKeys) {
    if (!potKeys.has(key)) {
      problems.push({
        locale: "pot",
        msgid: key,
        message: "used in src/ but not in messages.pot: run make i18n-extract",
      });
    }
  }
  for (const key of potKeys) {
    if (!extractedKeys.has(key)) {
      problems.push({
        locale: "pot",
        msgid: key,
        message: "in messages.pot but no longer used: run make i18n-extract",
      });
    }
  }
  return problems;
}

/**
 * One translated catalog against the template: every message present,
 * translated and not fuzzy; the same {placeholders} and <n> tags as the msgid; Plural-Forms set
 * when plurals exist; no obsolete entries.
 */
export function checkCatalog(
  locale: SupportedLocale,
  pot: PoFile,
  catalog: PoFile,
): CheckProblem[] {
  const problems: CheckProblem[] = [];
  const byKey = new Map(catalog.entries.map((entry) => [keyOf(entry), entry]));
  const potKeys = new Set(pot.entries.map(keyOf));

  if (catalog.obsoleteCount > 0) {
    problems.push({
      locale,
      message: `${catalog.obsoleteCount} obsolete #~ entries: run make i18n-extract`,
    });
  }
  for (const entry of catalog.entries) {
    if (!potKeys.has(keyOf(entry))) {
      problems.push({
        locale,
        msgid: entry.msgid,
        message: "not in messages.pot: run make i18n-extract",
      });
    }
  }
  if (
    catalog.entries.some((entry) => entry.plural) &&
    !(catalog.headers["Plural-Forms"] ?? "").includes("nplurals")
  ) {
    problems.push({
      locale,
      message: "plural messages exist but the Plural-Forms header is empty",
    });
  }
  for (const source of pot.entries) {
    const entry = byKey.get(keyOf(source));
    if (!entry) {
      problems.push({
        locale,
        msgid: source.msgid,
        message: "missing from the catalog: run make i18n-extract",
      });
      continue;
    }
    if (entry.fuzzy) {
      problems.push({
        locale,
        msgid: source.msgid,
        message: "fuzzy (English text changed): re-translate",
      });
      continue;
    }
    if (entry.msgstr === "") {
      problems.push({ locale, msgid: source.msgid, message: "not translated" });
      continue;
    }
    for (const form of entry.pluralForms) {
      if (!sameList(placeholdersOf(form), placeholdersOf(source.msgid))) {
        problems.push({
          locale,
          msgid: source.msgid,
          message: `placeholders differ: ${JSON.stringify(form)}`,
        });
      }
      if (!sameList(tagsOf(form), tagsOf(source.msgid))) {
        problems.push({
          locale,
          msgid: source.msgid,
          message: `<n> tags differ: ${JSON.stringify(form)}`,
        });
      }
    }
  }
  return problems;
}
