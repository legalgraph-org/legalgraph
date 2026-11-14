import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphData, type GraphEdge, type GraphNode } from "../../src/lib/graph-model";
import { LazyGraph } from "../../src/scripts/graph-view";

const nodes: GraphNode[] = [
  { id: "DE", label: "DE", title: "Germany", type: "country" },
  { id: "DE-DDG", label: "DDG", title: "DDG", type: "act" },
  { id: "DE-DDG-s5-1", label: "§ 5 Abs. 1 DDG", title: "§ 5 Abs. 1 DDG", type: "provision", law: "DE-DDG" },
  { id: "DE-DDG-s6-1", label: "§ 6 Abs. 1 DDG", title: "§ 6 Abs. 1 DDG", type: "provision", law: "DE-DDG" },
  { id: "VatId", label: "VAT ID", title: "VAT ID", type: "item" },
];
const edges: GraphEdge[] = [
  { source: "DE-DDG", target: "DE", label: "enacted in" },
  { source: "DE-DDG-s5-1", target: "DE-DDG", label: "part of" },
  { source: "DE-DDG-s6-1", target: "DE-DDG", label: "part of" },
  { source: "DE-DDG-s5-1", target: "VatId", label: "requires" },
];

describe("GraphData", () => {
  const graph = new GraphData(nodes, edges);

  it("gives the edges among a set of nodes once each", () => {
    expect(graph.edgesAmong(new Set(["DE-DDG", "DE-DDG-s5-1", "VatId"]))).toEqual([edges[1], edges[3]]);
  });

  it("finds a provision's law from its node or its edges", () => {
    expect(graph.partOf("DE-DDG-s6-1")).toBe("DE-DDG");
    expect(new GraphData(nodes.map(({ law: _law, ...node }) => node), edges).partOf("DE-DDG-s6-1")).toBe("DE-DDG");
    expect(graph.withParents(["DE-DDG-s5-1", "DE-DDG-s6-1"])).toEqual(new Set(["DE-DDG-s5-1", "DE-DDG-s6-1", "DE-DDG"]));
  });

  it("does not add an edge twice", () => {
    const grown = new GraphData(nodes, edges);
    grown.addEdges([edges[0]!, edges[0]!]);
    expect(grown.edgesOf("DE")).toHaveLength(1);
  });
});

describe("LazyGraph", () => {
  // The files /graph-node/<id>.json would hold, from the edges above.
  const shard = (id: string) => ({
    edges: edges
      .filter((edge) => edge.source === id || edge.target === id)
      .map((edge) => (edge.source === id ? [edge.label, edge.target, 1] : [edge.label, edge.source, 0])),
    properties: [["Id", id]],
  });

  afterEach(() => vi.unstubAllGlobals());

  it("knows every node at once and a node's edges once it is loaded, fetching each node once", async () => {
    const fetched: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      fetched.push(url);
      const id = decodeURIComponent(url.replace(/^\/graph-node\/(.*)\.json$/, "$1"));
      return Promise.resolve(new Response(JSON.stringify(shard(id))));
    });
    const graph = new LazyGraph(nodes, [], {}, {});
    expect(graph.nodes.size).toBe(5);
    expect(graph.connections("DE-DDG-s5-1")).toEqual([]);

    await graph.ensure(["DE-DDG-s5-1"]);
    expect(graph.neighbours("DE-DDG-s5-1")).toEqual(["DE-DDG", "VatId"]);
    expect(graph.properties("DE-DDG-s5-1")).toEqual([["Id", "DE-DDG-s5-1"]]);

    await graph.ensure(["DE-DDG-s5-1", "DE-DDG", "unknown"]);
    expect(fetched).toEqual(["/graph-node/DE-DDG-s5-1.json", "/graph-node/DE-DDG.json"]);
    expect(graph.neighbours("DE-DDG")).toEqual(["DE", "DE-DDG-s5-1", "DE-DDG-s6-1"]);
    // An edge both ends of which are loaded is known once.
    expect(graph.edgesOf("DE-DDG-s5-1")).toHaveLength(2);
  });

  it("tries a failed node again", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", () => {
      calls += 1;
      return Promise.resolve(calls === 1 ? new Response("", { status: 503 }) : new Response(JSON.stringify(shard("DE"))));
    });
    const graph = new LazyGraph(nodes, [], {}, {});
    await expect(graph.ensure(["DE"])).rejects.toThrow("503");
    await graph.ensure(["DE"]);
    expect(graph.neighbours("DE")).toEqual(["DE-DDG"]);
  });
});
