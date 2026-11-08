import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { extractMessages, type ExtractionProblem } from "../../scripts/i18n/extractor";
import { translatableSources } from "../../scripts/i18n/sources";

const fixture = (name: string) => {
  const path = join("tests/i18n/fixtures", name);
  return { path, source: readFileSync(path, "utf8") };
};

describe("extractMessages (.astro)", async () => {
  const { path, source } = fixture("Page.astro");
  const { messages, problems } = await extractMessages(path, source);

  it("finds calls in frontmatter and template, with context and source lines", () => {
    expect(messages).toEqual([
      { msgid: "Frontmatter message", reference: `${path}:5` },
      { msgid: "Menu", reference: `${path}:6` },
      { msgid: "Close", reference: `${path}:6` },
      { msgid: "Free", context: "pricing", reference: `${path}:10` },
      { msgid: "In the template", reference: `${path}:10` },
      { msgid: "Nested in a map", reference: `${path}:11` },
      { msgid: "Backtick without placeholders", reference: `${path}:12` },
    ]);
  });

  it("rejects a multi-line literal and allows passing t on under its own name", () => {
    expect(problems).toEqual([
      expect.objectContaining({
        severity: "error",
        message: "multi-line message literals are not allowed",
      }),
    ]);
  });
});

describe("extractMessages (rule violations)", async () => {
  const { path, source } = fixture("violations.ts");
  const { messages, problems } = await extractMessages(path, source);
  const errors = problems
    .filter((p) => p.severity === "error")
    .map((p) => `${p.reference} ${p.message}`);

  it("reports non-literal arguments", () => {
    const literalErrors = errors.filter((e) => e.includes("must be string literals"));
    expect(literalErrors.map((e) => e.split(" ")[0])).toEqual([
      `${path}:8`,
      `${path}:9`,
      `${path}:10`,
      `${path}:14`,
    ]);
  });

  it("reports every way of renaming t", () => {
    const renames = errors.filter((e) => e.includes("must not be renamed"));
    expect(renames.map((e) => e.split(" ")[0])).toEqual([`${path}:4`, `${path}:5`, `${path}:6`]);
  });

  it("does not extract calls made through another name", () => {
    expect(messages.map((m) => m.msgid)).not.toContain("Aliased");
    expect(messages.map((m) => m.msgid)).not.toContain("Renamed");
  });
});

describe("extractMessages (length)", async () => {
  const { path, source } = fixture("long.ts");
  const { messages, problems } = await extractMessages(path, source);

  it("extracts a long message but warns", () => {
    expect(messages).toHaveLength(1);
    expect(problems).toEqual([expect.objectContaining({ severity: "warning" })]);
  });
});

describe("extractMessages (edge whitespace)", async () => {
  const path = "src/Spacing.ts";
  const { messages, problems } = await extractMessages(path, 'const s = t(" (translation)");\n');

  it("rejects a message that starts or ends with whitespace", () => {
    expect(messages).toEqual([]);
    expect(problems).toEqual([
      expect.objectContaining({ severity: "error", reference: `${path}:1` }),
    ]);
  });
});

describe("extractMessages (client script with top-level await)", async () => {
  const path = "tests/i18n/fixtures/AwaitScript.astro";
  const source = [
    "---",
    'const title = t("Graph");',
    "---",
    "<h1>{title}</h1>",
    "<script>",
    "  const data = await fetch('/data.json');",
    "  console.log(data);",
    "</script>",
    "",
  ].join("\n");
  const { messages, problems } = await extractMessages(path, source);

  it("parses a module script that awaits at its top level", () => {
    expect(problems).toEqual([]);
    expect(messages).toEqual([{ msgid: "Graph", reference: `${path}:2` }]);
  });
});

describe("extractMessages (every site source)", async () => {
  const errors: ExtractionProblem[] = [];
  for (const path of translatableSources(process.cwd())) {
    const { problems } = await extractMessages(path, readFileSync(path, "utf8"));
    errors.push(...problems.filter((problem) => problem.severity === "error"));
  }

  it("extracts every .astro and .ts file under src/ without an error", () => {
    expect(errors).toEqual([]);
  });
});
