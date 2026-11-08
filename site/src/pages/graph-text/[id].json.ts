// The text of one provision for the graph view's reading panel (/graph-text/<id>.json): the quote
// in its own language and its counterpart, the English translation or, for acts authentic in
// several languages (EU law), the other language version. One small file per provision, fetched
// when its node is selected.
import type { APIRoute, GetStaticPaths } from "astro";
import { loadGraph, type Provision } from "../../lib/data";
import { METHOD } from "../../lib/links";

export const getStaticPaths = (async () => {
  const graph = await loadGraph();
  return [...graph.provisions.values()]
    .filter((provision) => provision.data.quotes.length > 0)
    .map((provision) => ({ params: { id: provision.id }, props: { provision } }));
}) satisfies GetStaticPaths;

export const GET: APIRoute = ({ props }) => {
  const { provision } = props as { provision: Provision };
  const quote = provision.data.quotes[0]!;
  const version = quote.versions[0];
  const translation = quote.translation;
  const counterpart = version
    ? { kind: "version", lang: version.lang, text: version.text, official: version.official, sourceUrl: version.sourceUrl }
    : translation?.text
      ? {
          kind: "translation",
          lang: "en",
          text: translation.text,
          method: METHOD[translation.method] ?? translation.method,
          status: translation.status,
        }
      : null;
  const body = {
    citation: provision.data.citation,
    original: { lang: quote.lang, text: quote.text, official: quote.official, sourceUrl: quote.sourceUrl, retrievedOn: quote.retrievedOn },
    counterpart,
  };
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
};
