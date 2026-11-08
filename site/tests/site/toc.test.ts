import { describe, expect, it } from "vitest";

import { tableOfContents } from "../../src/components/ds/toc";

describe("tableOfContents", () => {
  it("nests each h3 under the h2 before it", () => {
    const { groups } = tableOfContents('<h2 id="a">A</h2><p>x</p><h3 id="a1">A1</h3><h3 id="a2">A2</h3><h2 id="b">B</h2>');
    expect(groups).toEqual([
      { id: "a", text: "A", children: [{ id: "a1", text: "A1" }, { id: "a2", text: "A2" }] },
      { id: "b", text: "B", children: [] },
    ]);
  });

  it("keeps Markdown's ids and gives hand-written headings a unique slug", () => {
    const { html, groups } = tableOfContents(
      '<h2 id="licences">Licences</h2><h2 class="!mt-6">1. The original is kept, and locked</h2><h2>Licences</h2>',
    );
    expect(groups.map((group) => group.id)).toEqual(["licences", "1-the-original-is-kept-and-locked", "licences-1"]);
    expect(html).toContain('<h2 id="1-the-original-is-kept-and-locked" class="!mt-6">');
    expect(html).toContain('<h2 id="licences-1">Licences</h2>');
  });

  it("reads the text without tags or entities", () => {
    const { groups } = tableOfContents("<h2>Run <code>sources&nbsp;verify</code> &amp; check &#8220;it&#8221;</h2>");
    expect(groups[0].text).toBe("Run sources verify & check “it”");
  });

  it("leaves other headings and the rest of the text alone", () => {
    const source = "<h1>Title</h1><h4>Small</h4><p>Body</p>";
    expect(tableOfContents(source)).toEqual({ html: source, groups: [] });
  });
});
