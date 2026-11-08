import { describe, expect, it } from "vitest";

import { requireLocale } from "../../src/i18n/locales";
import { messageKey, placeholdersOf, tagsOf } from "../../src/i18n/message";
import { parsePo, usableTranslations } from "../../src/i18n/po";
import { parseRichText } from "../../src/i18n/rich-text";
import { translator } from "../../src/i18n/t";

const PO = `msgid ""
msgstr ""
"Language: de\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "Monthly"
msgstr "Monatlich"

#, fuzzy
#| msgid "Yearly billing"
msgid "Yearly"
msgstr "Jährliche Abrechnung"

msgid "Untranslated"
msgstr ""

msgctxt "pricing"
msgid "Free"
msgstr "Kostenlos"

msgid "Created in {minutes} minutes"
msgstr "In {minutes} Minuten erstellt"

#~ msgid "Gone"
#~ msgstr "Weg"
`;

describe("translator", () => {
  const catalog = usableTranslations(parsePo(PO));
  const t = translator("de", catalog);

  it("translates by English text", () => {
    expect(t("Monthly")).toBe("Monatlich");
  });

  it("treats fuzzy entries as missing and falls back to English", () => {
    expect(t("Yearly")).toBe("Yearly");
  });

  it("falls back to English for untranslated entries", () => {
    expect(t("Untranslated")).toBe("Untranslated");
  });

  it("uses msgctxt", () => {
    expect(t.ctx("pricing", "Free")).toBe("Kostenlos");
    expect(t("Free")).toBe("Free");
  });

  it("interpolates placeholders and requires every value", () => {
    expect(t("Created in {minutes} minutes", { minutes: 4 })).toBe("In 4 Minuten erstellt");
    expect(() => t("Created in {minutes} minutes")).toThrow(/needs a value for \{minutes\}/);
  });

  it("normalises whitespace in the lookup", () => {
    expect(t("  Monthly ")).toBe("Monatlich");
    expect(messageKey("a \n  b")).toBe("a b");
  });
});

describe("parsePo", () => {
  it("counts obsolete entries and reads fuzzy flags", () => {
    const file = parsePo(PO);
    expect(file.obsoleteCount).toBe(1);
    expect(file.entries.find((e) => e.msgid === "Yearly")?.fuzzy).toBe(true);
  });
});

describe("requireLocale", () => {
  it("narrows supported locales and throws otherwise", () => {
    expect(requireLocale("de")).toBe("de");
    expect(() => requireLocale(undefined)).toThrow(/Unsupported locale/);
    expect(() => requireLocale("fr")).toThrow(/Unsupported locale/);
  });
});

describe("rich text", () => {
  it("splits numbered tags", () => {
    expect(parseRichText("Read our <0>Privacy Policy</0> and <1>Terms</1>.")).toEqual([
      { kind: "text", text: "Read our " },
      { kind: "tag", index: 0, text: "Privacy Policy" },
      { kind: "text", text: " and " },
      { kind: "tag", index: 1, text: "Terms" },
      { kind: "text", text: "." },
    ]);
  });

  it("rejects nested, unbalanced and attributed tags", () => {
    expect(() => parseRichText("<0>a <1>b</1></0>")).toThrow(/Malformed/);
    expect(() => parseRichText("<0>open")).toThrow(/Malformed/);
    expect(() => parseRichText('<0 href="x">a</0>')).toThrow(/Malformed/);
  });

  it("lists placeholders and tags for the check", () => {
    expect(placeholdersOf("{b} and {a} and {a}")).toEqual(["a", "b"]);
    expect(tagsOf("<1>x</1> <0>y</0>")).toEqual([0, 1]);
  });
});
