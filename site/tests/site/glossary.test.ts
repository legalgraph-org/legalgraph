import { describe, expect, it } from "vitest";

import { markAbbreviations, type GlossaryEntry } from "../../src/lib/glossary-markup";

const entry = (id: string, match: string[]): GlossaryEntry => ({
  id,
  term: match[0]!,
  kind: "standard",
  seeAlso: [],
  match,
  expansion: `${id} expanded`,
  short: `${id} in one sentence.`,
  body: [],
});
const entries = [entry("eu", ["EU"]), entry("json", ["JSON"]), entry("json-ld", ["JSON-LD"]), entry("eur-lex", ["EUR-Lex"])];
const marked = (html: string) => markAbbreviations(html, entries, "en");
const ids = (html: string) => [...html.matchAll(/glossary#([\w-]+)/g)].map((match) => match[1]);

describe("markAbbreviations", () => {
  it("marks only the first use of each term", () => {
    expect(ids(marked("<p>EU law. The EU again.</p>"))).toEqual(["eu"]);
  });

  it("reads the longest spelling and whole words only", () => {
    expect(ids(marked("<p>JSON-LD, then EUR-Lex, then JSON.</p>"))).toEqual(["json-ld", "eur-lex", "json"]);
    expect(ids(marked("<p>EUROPE and eu</p>"))).toEqual([]);
  });

  it("marks a term before a hyphen, not after one", () => {
    expect(ids(marked("<p>the EU-US framework</p>"))).toEqual(["eu"]);
    expect(ids(marked("<p>non-EU</p>"))).toEqual([]);
  });

  it("leaves links, code, headings, figures and attributes alone", () => {
    const html = '<h2>EU</h2><a href="/EU">EU</a><code>JSON</code><figure><p>EU</p></figure><p title="EU">text</p>';
    expect(marked(html)).toBe(html);
  });

  it("escapes what it writes", () => {
    const tricky = [{ ...entry("eu", ["EU"]), short: 'A "union" <of> states & more.' }];
    expect(markAbbreviations("<p>EU</p>", tricky, "en")).toContain("A &quot;union&quot; &lt;of&gt; states &amp; more.");
  });
});
