/**
 * Fills a catalog's untranslated entries from a JSON object { msgid: translation }, e.g. one written by
 * a translator or a translation tool: bun scripts/i18n/fill.ts de translations.json
 * Existing translations are kept; msgids the catalog doesn't have are reported.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { po } from "gettext-parser";

import { LOCALES_DIR } from "../../src/i18n/catalog";

const [locale, jsonPath] = process.argv.slice(2);
if (!locale || !jsonPath) {
  console.error("usage: bun scripts/i18n/fill.ts <locale> <translations.json>");
  process.exit(2);
}
const poPath = join(LOCALES_DIR, `${locale}.po`);
const catalog = po.parse(readFileSync(poPath));
const translations: Record<string, string> = JSON.parse(readFileSync(jsonPath, "utf8"));
const used = new Set<string>();
let filled = 0;
for (const messages of Object.values(catalog.translations)) {
  for (const [msgid, message] of Object.entries(messages)) {
    const translation = translations[msgid];
    if (msgid === "" || translation === undefined) continue;
    used.add(msgid);
    if ((message.msgstr[0] ?? "") === "") {
      message.msgstr = [translation];
      filled += 1;
    }
  }
}
catalog.charset = "utf-8";
catalog.headers["Content-Type"] = "text/plain; charset=UTF-8";
writeFileSync(poPath, po.compile(catalog, { foldLength: 0 }));
const unused = Object.keys(translations).filter((msgid) => !used.has(msgid));
for (const msgid of unused) console.warn(`not in ${locale}.po: ${JSON.stringify(msgid)}`);
console.log(`${locale}.po: ${filled} entries filled`);
