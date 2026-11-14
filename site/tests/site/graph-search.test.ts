import { describe, expect, it } from "vitest";

import { GraphSearch, fold, words, type SearchNode } from "../../src/lib/graph-search";

const node = (id: string, label: string, type: string, law?: string): SearchNode => ({ id, label, title: label, type, ...(law ? { law } : {}) });

const nodes: SearchNode[] = [
  node("EU-2016-679", "GDPR", "act"),
  node("EU-2016-679-art6-1", "Art. 6(1) GDPR", "provision", "EU-2016-679"),
  node("EU-2016-679-art13-1", "Art. 13(1) GDPR", "provision", "EU-2016-679"),
  node("EU-2016-679-art60", "Art. 60 GDPR", "provision", "EU-2016-679"),
  node("DE-DDG", "DDG", "act"),
  node("DE-DDG-s5-1", "§ 5 Abs. 1 DDG", "provision", "DE-DDG"),
  node("GdprEprivacy", "Relationship between the GDPR and the ePrivacy Directive", "concept"),
  node("DE", "Germany", "country"),
  node("AT-ECG", "ECG", "act"),
];
const terms = {
  "EU-2016-679": ["DSGVO", "Datenschutz-Grundverordnung", "General Data Protection Regulation"],
  GdprEprivacy: ["Verhältnis von DSGVO und ePrivacy-Richtlinie"],
  DE: ["Deutschland"],
  "AT-ECG": ["E-Commerce-Gesetz"],
};
const search = new GraphSearch(nodes, terms);
const ids = (query: string) => search.find(query).hits.map((hit) => hit.node.id);

describe("words", () => {
  it("folds case, accents and ß, and drops punctuation", () => {
    expect(fold("Straße Öffnung")).toBe("strasse offnung");
    expect(words("§ 5 Abs. 1 DDG")).toEqual(["5", "abs", "1", "ddg"]);
    expect(words("Art. 6(1)(c) GDPR")).toEqual(["art", "6", "1", "c", "gdpr"]);
  });
});

describe("GraphSearch", () => {
  it("finds a law by an abbreviation in another language, first, with the name that matched", () => {
    const { hits } = search.find("DSGVO");
    expect(hits[0]?.node.id).toBe("EU-2016-679");
    expect(hits[0]?.alias).toBe("DSGVO");
    // Then what mentions it by name, then the law's provisions.
    expect(hits[1]?.node.id).toBe("GdprEprivacy");
    expect(hits.slice(2).map((hit) => hit.node.id)).toEqual(["EU-2016-679-art6-1", "EU-2016-679-art13-1", "EU-2016-679-art60"]);
  });

  it("finds a provision by its law's other name", () => {
    expect(ids("Art 6 DSGVO")).toEqual(["EU-2016-679-art6-1"]);
    expect(ids("art 13 datenschutz")).toEqual(["EU-2016-679-art13-1"]);
  });

  it("matches numbers whole, except the last one while it is typed", () => {
    expect(ids("art 6 gdpr")).toEqual(["EU-2016-679-art6-1"]);
    expect(ids("gdpr art 6")).toEqual(["EU-2016-679-art6-1", "EU-2016-679-art60"]);
  });

  it("matches the start of words, ignoring case and punctuation", () => {
    expect(ids("§5 ddg")).toEqual(["DE-DDG-s5-1"]);
    expect(ids("deutsch")).toEqual(["DE"]);
    expect(ids("e-commerce")).toEqual(["AT-ECG"]);
    // The law, then its provisions (found by its name).
    expect(ids("general data")[0]).toBe("EU-2016-679");
    expect(ids("general data")).toHaveLength(4);
    expect(ids("tection")).toEqual([]);
  });

  it("finds a node by its identifier, whole or its beginning", () => {
    expect(ids("DE-DDG-s5-1")).toEqual(["DE-DDG-s5-1"]);
    expect(ids("EU-2016-679-art")).toEqual(["EU-2016-679-art6-1", "EU-2016-679-art13-1", "EU-2016-679-art60"]);
    // Without a hyphen, a word: "de" is the start of Deutschland, not of every German id.
    expect(ids("de")).toEqual(["DE"]);
  });

  it("puts an exact name first, then names that start with the query", () => {
    expect(ids("ddg")).toEqual(["DE-DDG", "DE-DDG-s5-1"]);
  });

  it("caps the list and counts every match", () => {
    expect(search.find("gdpr", 2)).toMatchObject({ total: 5 });
    expect(search.find("gdpr", 2).hits).toHaveLength(2);
    expect(search.find("   ")).toEqual({ hits: [], total: 0 });
  });
});
