/** make i18n-check: the CI gate for translations. Exits non-zero on any problem. */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { LOCALES_DIR } from "../../src/i18n/catalog";
import { TRANSLATED_LOCALES } from "../../src/i18n/locales";
import { messageKey } from "../../src/i18n/message";
import { readPo } from "../../src/i18n/po";
import { checkCatalog, checkTemplate, type CheckProblem } from "./checker";
import { extractMessages } from "./extractor";
import { translatableSources } from "./sources";

const root = process.cwd();
const extractedKeys = new Set<string>();
for (const path of translatableSources(root)) {
  const { messages } = await extractMessages(path, readFileSync(join(root, path), "utf8"));
  for (const message of messages) {
    extractedKeys.add(messageKey(message.msgid, message.context));
  }
}

const pot = readPo(join(LOCALES_DIR, "messages.pot"));
const problems: CheckProblem[] = [
  ...checkTemplate(pot, extractedKeys),
  ...TRANSLATED_LOCALES.flatMap((locale) =>
    checkCatalog(locale, pot, readPo(join(LOCALES_DIR, `${locale}.po`))),
  ),
];

for (const problem of problems) {
  console.error(
    `${problem.locale}: ${problem.message}${problem.msgid ? `\n    ${JSON.stringify(problem.msgid)}` : ""}`,
  );
}
if (problems.length > 0) {
  console.error(`i18n-check: ${problems.length} problem(s)`);
  process.exit(1);
}
console.log(
  `i18n-check: ${pot.entries.length} messages, ${TRANSLATED_LOCALES.join(", ")} complete`,
);
