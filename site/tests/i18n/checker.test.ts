import { describe, expect, it } from "vitest";

import { checkCatalog, checkTemplate } from "../../scripts/i18n/checker";
import { parsePo } from "../../src/i18n/po";

const POT = parsePo(`msgid ""
msgstr ""

msgid "Monthly"
msgstr ""

msgid "Read our <0>Privacy Policy</0>."
msgstr ""

msgid "Created in {minutes} minutes"
msgstr ""
`);

const catalog = (body: string) => parsePo(`msgid ""\nmsgstr ""\n"Language: de\\n"\n\n${body}`);

describe("checkCatalog", () => {
  it("accepts a complete catalog", () => {
    const de = catalog(`msgid "Monthly"
msgstr "Monatlich"

msgid "Read our <0>Privacy Policy</0>."
msgstr "Lesen Sie unsere <0>Datenschutzerklärung</0>."

msgid "Created in {minutes} minutes"
msgstr "In {minutes} Minuten erstellt"
`);
    expect(checkCatalog("de", POT, de)).toEqual([]);
  });

  it("fails on fuzzy, missing, untranslated, tag and placeholder drift, and obsolete entries", () => {
    const de = catalog(`#, fuzzy
msgid "Monthly"
msgstr "Monatlich"

msgid "Read our <0>Privacy Policy</0>."
msgstr "Lesen Sie unsere Datenschutzerklärung."

msgid "Stale"
msgstr "Alt"

#~ msgid "Gone"
#~ msgstr "Weg"
`);
    const messages = checkCatalog("de", POT, de).map((p) => `${p.msgid ?? ""}: ${p.message}`);
    expect(messages).toEqual([
      ": 1 obsolete #~ entries: run make i18n-extract",
      "Stale: not in messages.pot: run make i18n-extract",
      "Monthly: fuzzy (English text changed): re-translate",
      'Read our <0>Privacy Policy</0>.: <n> tags differ: "Lesen Sie unsere Datenschutzerklärung."',
      "Created in {minutes} minutes: missing from the catalog: run make i18n-extract",
    ]);
  });

  it("catches a placeholder renamed by the translator", () => {
    const de = catalog(`msgid "Monthly"
msgstr "Monatlich"

msgid "Read our <0>Privacy Policy</0>."
msgstr "Lesen Sie unsere <0>Datenschutzerklärung</0>."

msgid "Created in {minutes} minutes"
msgstr "In {minuten} Minuten erstellt"
`);
    expect(checkCatalog("de", POT, de)).toEqual([
      expect.objectContaining({ message: 'placeholders differ: "In {minuten} Minuten erstellt"' }),
    ]);
  });
});

describe("checkTemplate", () => {
  it("reports a stale messages.pot in both directions", () => {
    const used = new Set(["Monthly", "Created in {minutes} minutes", "New message"]);
    expect(checkTemplate(POT, used).map((p) => p.msgid)).toEqual([
      "New message",
      "Read our <0>Privacy Policy</0>.",
    ]);
  });
});
