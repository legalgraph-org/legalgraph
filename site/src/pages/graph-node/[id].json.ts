// One node of the graph view (/graph-node/<id>.json): its edges and its properties, fetched when the
// view first shows, expands or selects the node (lib/graph-export.ts).
import type { APIRoute, GetStaticPaths } from "astro";

import { nodeShard, wholeGraph } from "../../lib/graph-export";

export const getStaticPaths = (() => [...wholeGraph().nodes.keys()].map((id) => ({ params: { id } }))) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ params }) =>
  new Response(JSON.stringify(await nodeShard(params.id!)), { headers: { "Content-Type": "application/json" } });
