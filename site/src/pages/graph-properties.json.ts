// The plain properties of every node in the graph view (/graph-properties.json): what a property
// graph shows when a node is selected. Values are text; links are URLs. Fetched the first time a
// node is selected, so the graph itself stays small.
import type { APIRoute } from "astro";
import { loadGraph, type Act } from "../lib/data";
import { languageName, STATUS } from "../lib/links";

type Property = [string, string];

export const GET: APIRoute = async () => {
  const graph = await loadGraph();
  const jurisdiction = (id: string) => graph.jurisdictions.get(id)?.data.label ?? id;
  const concept = (id: string) => graph.concepts.get(id)?.data.label ?? id;
  const status = (id: string) => STATUS[id]?.label ?? id;
  // A law by all its names: "TKG 2021 · Telekommunikationsgesetz 2021 · Telecommunications Act 2021".
  const lawName = (act: Act) => {
    const own = act.data.titles.find((t) => t.lang !== "en")?.text ?? act.data.titles[0]?.text;
    const english = act.data.titleEn;
    return [act.data.shortName, own, english !== own && english].filter(Boolean).join(" · ");
  };
  const properties: Record<string, Property[]> = {};
  const set = (id: string, values: [string, string | number | null | undefined | false][]) => {
    properties[id] = values.filter((pair): pair is [string, string | number] => pair[1] !== null && pair[1] !== undefined && pair[1] !== false && pair[1] !== "").map(([key, value]) => [key, String(value)]);
  };

  for (const j of graph.jurisdictions.values()) {
    const d = j.data;
    set(j.id, [
      ["Code", d.code],
      ["Kind", d.kind],
      ["Member of", d.memberOf.map(jurisdiction).join(", ")],
      ["Members", d.members.length || null],
      ["Official languages", d.languages.map(languageName).join(", ")],
      ["Notice called", d.noticeNames.map((n) => n.text).join(", ")],
      ["Laws in the graph", d.acts.length],
      ["Note", d.comment],
    ]);
  }
  for (const a of graph.acts.values()) {
    const d = a.data;
    const original = d.titles[0]?.text;
    set(a.id, [
      ["Title", original],
      ["English title", d.titleEn !== original && d.titleEn],
      ["Short name", d.shortName],
      ["Type", concept(d.actType)],
      ["Jurisdiction", jurisdiction(d.jurisdiction)],
      ["Official number", d.localId],
      ["ECLI", d.ecli],
      ["Date", d.dateDocument],
      ["In force since", d.firstInForce],
      ["No longer in force", d.noLongerInForce],
      ["Provisions in the graph", d.provisions.length],
      ["Source files", d.documents.length],
      ["Review status", status(d.reviewStatus)],
      ["Official text", d.sourceUrl],
    ]);
  }
  for (const p of graph.provisions.values()) {
    const d = p.data;
    const act = graph.acts.get(d.act);
    set(p.id, [
      ["Citation", d.citation],
      ["Part of", act ? lawName(act) : d.act],
      ["Jurisdiction", jurisdiction(d.jurisdiction)],
      ["Quotes", d.quotes.length ? `${d.quotes.length} (${[...new Set(d.quotes.map((q) => languageName(q.lang)))].join(", ")})` : null],
      ["Review status", status(d.reviewStatus)],
      ["Official text", d.sourceUrl],
    ]);
  }
  const DEONTIC: Record<string, string> = { Must: "Obligation (must)", MustNot: "Prohibition (must not)", May: "Permission (may)" };
  for (const o of graph.obligations.values()) {
    const d = o.data;
    set(o.id, [
      ["Rule", d.label],
      ["Kind", DEONTIC[d.deonticType] ?? d.deonticType],
      ["Applies in", jurisdiction(d.appliesIn)],
      ["Addressed to", d.bearer.map(concept).join(", ")],
      ["Conditions", d.appliesWhen.length],
      ["Exemptions", d.unless.length || null],
      ["Information to disclose", d.items.length || null],
      ["Actions", d.actions.length || null],
      ["Review status", status(d.reviewStatus)],
      ["Note", d.comment],
    ]);
  }
  for (const c of graph.concepts.values()) {
    const d = c.data;
    set(c.id, [
      ["Label", d.label],
      ["Kind", d.kind],
      ["Scheme", d.scheme ? concept(d.scheme) : null],
      ["Also called", [...d.labels.filter((l) => l.text !== d.label), ...d.altLabels].map((l) => `${l.text} (${l.lang})`).join(", ")],
      ["Definition", d.definition],
      ["Question", d.question],
    ]);
  }
  return new Response(JSON.stringify(properties), { headers: { "Content-Type": "application/json" } });
};
