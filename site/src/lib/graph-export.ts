// What the build writes for the graph views, so no page has to download the whole graph:
//
//   /graph-index.json        every node (id, label, type, its law), the laws' names, the other
//                            names each node is found by (search), and the edges of the starting
//                            view (the jurisdictions). Fetched once by the graph view.
//   /graph-node/<id>.json    one node's edges and properties, fetched when the view needs that node.
//   a page's mini graph      its neighbourhood, written into the page itself (MiniGraph.astro).
//
// graph.json (written by `legalgraph generate-site`) is the source of nodes and edges; the content
// collections (lib/data.ts) and the glossary add names and properties.
import { getCollection } from "astro:content";

import { SUPPORTED_LOCALES } from "../i18n/locales";
import graphJson from "../data/graph.json";
import { loadGraph, type Act, type Graph } from "./data";
import { GraphData, type GraphEdge, type GraphNode, type LawName } from "./graph-model";
import { languageName, STATUS } from "./links";

export type Property = [string, string];

/** One node's file (/graph-node/<id>.json): its edges as [relation, other node, 1 if outgoing else 0]. */
export interface NodeShard {
  edges: [string, string, 0 | 1][];
  properties: Property[];
}

/** A node in the index: its title only where it differs from its label (a country: DE, Germany). */
export type IndexNode = Omit<GraphNode, "title"> & { title?: string };

export interface GraphIndex {
  nodes: IndexNode[];
  edges: GraphEdge[];
  laws: Record<string, LawName>;
  terms: Record<string, string[]>;
}

const JURISDICTION_TYPES = new Set(["country", "organisation"]);

let whole: GraphData | undefined;

/** The whole graph (nodes and edges of graph.json), with each provision's law. */
export function wholeGraph(): GraphData {
  if (!whole) {
    const plain = new GraphData(graphJson.nodes, graphJson.edges);
    const nodes = graphJson.nodes.map((node) => {
      const law = plain.partOf(node.id);
      return law ? { ...node, law } : node;
    });
    whole = new GraphData(nodes, graphJson.edges);
  }
  return whole;
}

/**
 * A page's mini graph: the node, at most `limit` of its neighbours, the laws they share, and the
 * edges between them. Undefined when the node is not in the graph.
 */
export function neighbourhood(id: string, limit: number): { ids: string[]; nodes: GraphNode[]; edges: GraphEdge[] } | undefined {
  const graph = wholeGraph();
  if (!graph.nodes.has(id)) return undefined;
  const ids = graph.around(id, limit);
  const all = graph.withParents(ids);
  return { ids: [...ids], nodes: [...all].map((other) => graph.nodes.get(other)!), edges: graph.edgesAmong(all) };
}

/** Every law, judgment and guideline by its names: short name, own-language title, English title. */
export function lawNames(graph: Graph): Record<string, LawName> {
  return Object.fromEntries(
    [...graph.acts.values()].map((act) => {
      const own = act.data.titles.find((title) => title.lang !== "en") ?? act.data.titles[0];
      const english = act.data.titleEn ?? act.data.titles.find((title) => title.lang === "en")?.text ?? null;
      return [
        act.id,
        {
          short: act.data.shortName,
          title: own?.text ?? english ?? act.id,
          lang: own?.lang ?? "en",
          english: english && english !== own?.text ? english : null,
        },
      ];
    }),
  );
}

/** A country's name in each of the site's languages ("Deutschland"), where the code is a region. */
function regionNames(code: string): string[] {
  return SUPPORTED_LOCALES.flatMap((locale) => {
    try {
      const name = new Intl.DisplayNames([locale], { type: "region", fallback: "none" }).of(code);
      return name ? [name] : [];
    } catch {
      return [];
    }
  });
}

/**
 * The names a node is found by besides its label and title: a law's abbreviations and titles in every
 * language (from the graph and the glossary: DSGVO for the GDPR), its official number, ECLI and case
 * number; a concept's labels in every language; a country's name in the site's languages.
 */
export async function searchTerms(graph: Graph): Promise<Record<string, string[]>> {
  const terms = new Map<string, Set<string>>();
  const add = (id: string, ...texts: (string | null | undefined)[]) => {
    if (!terms.has(id)) terms.set(id, new Set());
    for (const text of texts) if (text) terms.get(id)!.add(text);
  };
  for (const act of graph.acts.values()) {
    const d = act.data;
    add(act.id, d.shortName, d.titleEn, d.localId, d.ecli, d.caseNumber, ...d.titles.map((title) => title.text));
  }
  for (const concept of graph.concepts.values()) {
    const d = concept.data;
    add(concept.id, d.label, ...d.labels.map((label) => label.text), ...d.altLabels.map((label) => label.text));
  }
  for (const jurisdiction of graph.jurisdictions.values()) {
    const d = jurisdiction.data;
    add(jurisdiction.id, d.label, d.code, ...regionNames(d.code));
  }
  for (const { data } of await getCollection("glossary")) {
    if (!data.graph) continue;
    add(data.graph, data.original?.text, ...SUPPORTED_LOCALES.flatMap((locale) => [...data[locale].match, data[locale].expansion]));
  }
  const nodes = wholeGraph().nodes;
  return Object.fromEntries(
    [...terms]
      .filter(([id]) => nodes.has(id))
      .map(([id, texts]) => {
        const node = nodes.get(id)!;
        return [id, [...texts].filter((text) => text !== node.label && text !== node.title && text !== id)] as const;
      })
      .filter(([, texts]) => texts.length > 0),
  );
}

let index: Promise<GraphIndex> | undefined;

/** /graph-index.json: see the top of this file. */
export function graphIndex(): Promise<GraphIndex> {
  index ??= (async () => {
    const graph = await loadGraph();
    const whole = wholeGraph();
    const jurisdictions = new Set([...whole.nodes.values()].filter((node) => JURISDICTION_TYPES.has(node.type)).map((node) => node.id));
    return {
      nodes: [...whole.nodes.values()].map(({ title, ...node }): IndexNode => (title === node.label ? node : { ...node, title })),
      edges: whole.edgesAmong(jurisdictions),
      laws: lawNames(graph),
      terms: await searchTerms(graph),
    };
  })();
  return index;
}

/** /graph-node/<id>.json: a node's edges and properties. */
export async function nodeShard(id: string): Promise<NodeShard> {
  const properties = await nodeProperties();
  return {
    edges: wholeGraph()
      .edgesOf(id)
      .map((edge) => (edge.source === id ? [edge.label, edge.target, 1] : [edge.label, edge.source, 0])),
    properties: properties.get(id) ?? [],
  };
}

let propertiesOf: Promise<Map<string, Property[]>> | undefined;

/**
 * The plain properties of every node, as a property graph shows them when a node is selected.
 * Values are text; links are URLs.
 */
export function nodeProperties(): Promise<Map<string, Property[]>> {
  propertiesOf ??= loadGraph().then(collectProperties);
  return propertiesOf;
}

function collectProperties(graph: Graph): Map<string, Property[]> {
  const jurisdiction = (id: string) => graph.jurisdictions.get(id)?.data.label ?? id;
  const concept = (id: string) => graph.concepts.get(id)?.data.label ?? id;
  const status = (id: string) => STATUS[id]?.label ?? id;
  // A law by all its names: "TKG 2021 · Telekommunikationsgesetz 2021 · Telecommunications Act 2021".
  const lawName = (act: Act) => {
    const own = act.data.titles.find((t) => t.lang !== "en")?.text ?? act.data.titles[0]?.text;
    const english = act.data.titleEn;
    return [act.data.shortName, own, english !== own && english].filter(Boolean).join(" · ");
  };
  const properties = new Map<string, Property[]>();
  const set = (id: string, values: [string, string | number | null | undefined | false][]) => {
    properties.set(
      id,
      values
        .filter((pair): pair is [string, string | number] => pair[1] !== null && pair[1] !== undefined && pair[1] !== false && pair[1] !== "")
        .map(([key, value]) => [key, String(value)]),
    );
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
  return properties;
}
