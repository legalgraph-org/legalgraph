import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { translatableSources } from "../../scripts/i18n/sources";

// `href=pagePath("graph", t.locale)` without braces is not an error in Astro: the attribute becomes
// the text `pagePath("graph",` and the link breaks. An attribute whose unquoted value is a call or
// a property path must be written in braces.
const UNBRACED = /\s[\w:@-]+=[A-Za-z_$][\w$]*(?:\.[\w$]+)*[([]/g;

describe(".astro attributes", () => {
  it("write every expression in braces", () => {
    const found = translatableSources(process.cwd())
      .filter((path) => path.endsWith(".astro"))
      .flatMap((path) =>
        readFileSync(path, "utf8")
          .split("\n")
          .flatMap((line, i) => [...line.matchAll(UNBRACED)].map((m) => `${path}:${i + 1}:${m[0].trim()}`)),
      );
    expect(found).toEqual([]);
  });
});
