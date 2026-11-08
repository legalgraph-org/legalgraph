// schema.org markup for search engines: legal acts and provisions as schema.org/Legislation (which is
// aligned with ELI), so articles elsewhere (aimix.io) can cite them and search engines read them.
import { actLabel, actTitle, type Act, type Graph, type Provision } from "./data";
import { iri } from "./links";

const PUBLISHER = { "@type": "Organization", name: "Aimix GmbH", url: "https://aimix.io" };

export function actJsonLd(graph: Graph, act: Act): Record<string, unknown> {
  const a = act.data;
  const jurisdiction = graph.jurisdictions.get(a.jurisdiction)?.data.label ?? a.jurisdiction;
  return {
    "@context": "https://schema.org",
    "@type": a.kind === "act" ? "Legislation" : "CreativeWork",
    "@id": iri("id", act.id),
    name: actTitle(act),
    alternateName: actLabel(act),
    ...(a.localId && { legislationIdentifier: a.localId }),
    ...(a.kind === "act" && { legislationJurisdiction: jurisdiction, legislationType: a.actType }),
    ...(a.dateDocument && { legislationDate: a.dateDocument }),
    ...(a.lastAmended && { legislationDateVersion: a.lastAmended }),
    ...(a.sourceUrl && { sameAs: a.sourceUrl }),
    isAccessibleForFree: true,
    publisher: PUBLISHER,
    license: "https://creativecommons.org/licenses/by/4.0/",
  };
}

export function provisionJsonLd(graph: Graph, provision: Provision): Record<string, unknown> {
  const p = provision.data;
  const act = graph.acts.get(p.act);
  const quote = p.quotes[0];
  return {
    "@context": "https://schema.org",
    "@type": "Legislation",
    "@id": iri("id", provision.id),
    name: p.citation,
    legislationIdentifier: p.citation,
    ...(act && { isPartOf: { "@type": "Legislation", "@id": iri("id", act.id), name: actTitle(act) } }),
    ...(p.sourceUrl && { sameAs: p.sourceUrl }),
    ...(quote && { text: quote.text, inLanguage: quote.lang }),
    isAccessibleForFree: true,
    publisher: PUBLISHER,
    license: "https://creativecommons.org/licenses/by/4.0/",
  };
}
