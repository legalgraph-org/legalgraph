/**
 * make i18n-extract: src/ → locales/messages.pot → msgmerge into every locales/<locale>.po,
 * then drop obsolete entries.
 *
 *   bun scripts/i18n/extract.ts                      update existing catalogs
 *   bun scripts/i18n/extract.ts --seed <dir>         create missing catalogs and fill missing
 *                                                    messages from another set of catalogs
 *                                                    (msgmerge --compendium)
 */
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { LOCALES_DIR } from "../../src/i18n/catalog";
import { TRANSLATED_LOCALES } from "../../src/i18n/locales";
import { extractMessages, type ExtractedMessage, type ExtractionProblem } from "./extractor";
import {
  checkGettextVersion,
  dropFuzzy,
  msgmergeFromCompendium,
  msgmergeUpdate,
  pruneObsolete,
} from "./gettext";
import { ensureHeaders } from "./headers";
import { collectEntries, compilePot } from "./pot";
import { translatableSources } from "./sources";

const root = process.cwd();
const seedIndex = process.argv.indexOf("--seed");
const seedDir = seedIndex === -1 ? undefined : process.argv[seedIndex + 1];

checkGettextVersion();

const messages: ExtractedMessage[] = [];
const problems: ExtractionProblem[] = [];
for (const path of translatableSources(root)) {
  const result = await extractMessages(path, readFileSync(join(root, path), "utf8"));
  messages.push(...result.messages);
  problems.push(...result.problems);
}
for (const problem of problems) {
  console[problem.severity === "error" ? "error" : "warn"](
    `${problem.severity}: ${problem.reference}: ${problem.message}`,
  );
}
if (problems.some((problem) => problem.severity === "error")) {
  process.exit(1);
}

const entries = collectEntries(messages);
const potPath = join(LOCALES_DIR, "messages.pot");
writeFileSync(potPath, compilePot(entries));
console.log(
  `messages.pot: ${entries.length} messages from ${new Set(messages.map((m) => m.reference.split(":")[0])).size} files`,
);

for (const locale of TRANSLATED_LOCALES) {
  const poPath = join(LOCALES_DIR, `${locale}.po`);
  if (existsSync(poPath)) {
    if (seedDir) {
      dropFuzzy(poPath);
    }
    msgmergeUpdate(poPath, potPath, seedDir ? join(seedDir, `${locale}.po`) : undefined);
    if (seedDir) {
      console.log(`${locale}.po: missing messages filled from ${seedDir}/${locale}.po`);
    }
  } else if (seedDir) {
    msgmergeFromCompendium(poPath, potPath, join(seedDir, `${locale}.po`));
    console.log(`${locale}.po: created, seeded from ${seedDir}/${locale}.po`);
  } else {
    // A new catalog starts as the template, which carries the UTF-8 header: msgmerge against an
    // empty compendium (/dev/null) writes no header and drops every non-ASCII character.
    copyFileSync(potPath, poPath);
    msgmergeUpdate(poPath, potPath);
    console.log(`${locale}.po: created empty`);
  }
  pruneObsolete(poPath);
  ensureHeaders(poPath, locale);
}
console.log(
  "Next: translate the empty and fuzzy entries (a translator or a translation tool), then make i18n-check",
);
