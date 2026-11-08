// All collections, indexed for cross-references, loaded once per build.
import { getCollection, type CollectionEntry } from "astro:content";

import type { Quote } from "../content.config";
import { pagePath, type Space } from "./links";

export type Jurisdiction = CollectionEntry<"jurisdictions">;
export type Act = CollectionEntry<"acts">;
export type Provision = CollectionEntry<"provisions">;
export type Concept = CollectionEntry<"concepts">;
export type Document = CollectionEntry<"documents">;
export type Obligation = CollectionEntry<"obligations">;

export interface Resource {
  space: Space;
  id: string;
  href: string;
  label: string;
  kind: string;
}

export interface Graph {
  jurisdictions: Map<string, Jurisdiction>;
  acts: Map<string, Act>;
  provisions: Map<string, Provision>;
  concepts: Map<string, Concept>;
  documents: Map<string, Document>;
  obligations: Map<string, Obligation>;
  quotes: Map<string, { quote: Quote; provision: Provision }>;
}

let cached: Promise<Graph> | undefined;

export function loadGraph(): Promise<Graph> {
  cached ??= (async () => {
    const byId = <T extends { id: string }>(entries: T[]) => new Map(entries.map((entry) => [entry.id, entry]));
    const provisions = byId(await getCollection("provisions"));
    const quotes = new Map<string, { quote: Quote; provision: Provision }>();
    for (const provision of provisions.values()) {
      for (const quote of provision.data.quotes) {
        quotes.set(quote.id, { quote, provision });
        for (const version of quote.versions) quotes.set(version.id, { quote, provision });
      }
    }
    return {
      jurisdictions: byId(await getCollection("jurisdictions")),
      acts: byId(await getCollection("acts")),
      provisions,
      concepts: byId(await getCollection("concepts")),
      documents: byId(await getCollection("documents")),
      obligations: byId(await getCollection("obligations")),
      quotes,
    };
  })();
  return cached;
}

export function actLabel(act: Act): string {
  return act.data.shortName ?? act.data.titleEn ?? act.data.titles[0]?.text ?? act.id;
}

export function actTitle(act: Act): string {
  return act.data.titles.find((t) => t.lang !== "en")?.text ?? act.data.titleEn ?? act.id;
}

/** Any identifier in the graph, as a link target. */
export function resolve(graph: Graph, id: string): Resource {
  const link = (space: Space, label: string, kind: string): Resource => ({
    space,
    id,
    href: pagePath(space, id),
    label,
    kind,
  });
  const jurisdiction = graph.jurisdictions.get(id);
  if (jurisdiction) return link("id", jurisdiction.data.label, jurisdiction.data.kind);
  const act = graph.acts.get(id);
  if (act) return link("id", actLabel(act), "act");
  const provision = graph.provisions.get(id);
  if (provision) return link("id", provision.data.citation, "provision");
  const concept = graph.concepts.get(id);
  if (concept) return link("vocab", concept.data.label, concept.data.kind);
  const obligation = graph.obligations.get(id);
  if (obligation) return link("id", obligation.data.label, "rule");
  const document = graph.documents.get(id);
  if (document) return link("id", document.data.path.split("/").pop() ?? id, "source document");
  if (graph.quotes.has(id)) return link("id", `Quote of ${graph.quotes.get(id)!.provision.data.citation}`, "quote");
  return link("id", id, "resource");
}
