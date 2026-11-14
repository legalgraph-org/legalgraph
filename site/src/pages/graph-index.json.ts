// The graph view's starting point (/graph-index.json): every node, the laws' names, the names each
// node is found by, and the edges of the starting view. A node's own edges and properties are in
// /graph-node/<id>.json, fetched when the view needs them (lib/graph-export.ts).
import type { APIRoute } from "astro";

import { graphIndex } from "../lib/graph-export";

export const GET: APIRoute = async () =>
  new Response(JSON.stringify(await graphIndex()), { headers: { "Content-Type": "application/json" } });
