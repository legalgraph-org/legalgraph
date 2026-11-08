// Content negotiation for resource identifiers. Static files in dist/ are served directly;
// requests under /id/ and /vocab/ come here first.
// A browser asking for /id/DE-DDG gets the HTML page; a client sending `Accept: text/turtle`
// (or application/n-triples, application/rdf+xml) gets /id/DE-DDG.ttl.
const RDF_TYPES = /text\/turtle|application\/n-triples|application\/rdf\+xml|application\/ld\+json/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const accept = request.headers.get("Accept") ?? "";
    if (RDF_TYPES.test(accept) && !/\.\w+$/.test(url.pathname)) {
      url.pathname = `${url.pathname.replace(/\/$/, "")}.ttl`;
      const response = await env.ASSETS.fetch(new Request(url, request));
      if (response.ok) {
        const headers = new Headers(response.headers);
        headers.set("Content-Type", "text/turtle; charset=utf-8");
        headers.set("Access-Control-Allow-Origin", "*");
        headers.set("Vary", "Accept");
        return new Response(response.body, { status: 200, headers });
      }
    }
    const response = await env.ASSETS.fetch(request);
    const headers = new Headers(response.headers);
    headers.append("Vary", "Accept");
    headers.set("Link", `<${url.pathname.replace(/\/$/, "")}.ttl>; rel="alternate"; type="text/turtle"`);
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  },
};
