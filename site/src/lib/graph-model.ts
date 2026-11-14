// The graph as the views use it: nodes, edges and an index of each node's edges. No drawing here, so
// the build (pages, the mini graphs, the files the graph view fetches) and the browser share it.
//
// A GraphData can hold the whole graph (the build, a page's mini graph) or grow as it is explored
// (the graph view, scripts/graph-view.ts LazyGraph): every node is known from the start, and a
// node's edges once it is loaded. `ensure` loads nodes; for a whole graph there is nothing to load.

export interface GraphNode {
  id: string;
  label: string;
  title: string;
  type: string;
  /** The law (or judgment, or guideline) a provision is part of. */
  law?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

/** A law's names: short name, title in its own language, and English title (if different). */
export interface LawName {
  short: string | null;
  title: string;
  lang: string;
  english: string | null;
}

export interface Connection {
  edge: GraphEdge;
  other: GraphNode;
  outgoing: boolean;
}

export const edgeKey = (edge: GraphEdge) => `${edge.source}|${edge.label}|${edge.target}`;

export class GraphData {
  readonly nodes: Map<string, GraphNode>;
  private readonly adjacent = new Map<string, GraphEdge[]>();
  private readonly known = new Set<string>();
  private readonly parent = new Map<string, string>();

  constructor(
    nodes: Iterable<GraphNode>,
    edges: Iterable<GraphEdge> = [],
    readonly laws: Record<string, LawName> = {},
  ) {
    this.nodes = new Map([...nodes].map((node) => [node.id, node]));
    this.addEdges(edges);
  }

  /** Adds edges not known yet (an edge arrives with both of its nodes). */
  addEdges(edges: Iterable<GraphEdge>): void {
    for (const edge of edges) {
      const key = edgeKey(edge);
      if (this.known.has(key)) continue;
      this.known.add(key);
      for (const end of new Set([edge.source, edge.target])) {
        if (!this.adjacent.has(end)) this.adjacent.set(end, []);
        this.adjacent.get(end)!.push(edge);
      }
      if (edge.label === "part of" && !this.parent.has(edge.source)) this.parent.set(edge.source, edge.target);
    }
  }

  /** Makes sure the edges of these nodes are known. A whole graph knows them all already. */
  ensure(_ids: Iterable<string>): Promise<void> {
    return Promise.resolve();
  }

  /** The edges known to touch a node. */
  edgesOf(id: string): readonly GraphEdge[] {
    return this.adjacent.get(id) ?? [];
  }

  /** The known edges between the given nodes, each once. */
  edgesAmong(ids: ReadonlySet<string>): GraphEdge[] {
    const seen = new Set<string>();
    const edges: GraphEdge[] = [];
    for (const id of ids) {
      for (const edge of this.edgesOf(id)) {
        const key = edgeKey(edge);
        if (seen.has(key) || !ids.has(edge.source) || !ids.has(edge.target)) continue;
        seen.add(key);
        edges.push(edge);
      }
    }
    return edges;
  }

  connections(id: string): Connection[] {
    return this.edgesOf(id)
      .map((edge) => {
        const outgoing = edge.source === id;
        return { edge, outgoing, other: this.nodes.get(outgoing ? edge.target : edge.source)! };
      })
      .filter((connection) => connection.other)
      .sort((a, b) => a.edge.label.localeCompare(b.edge.label) || a.other.title.localeCompare(b.other.title));
  }

  /**
   * The node's neighbours, taking turns between kinds of relation (part of, implements, requires …)
   * so that a capped list still shows every kind, not the first fifty of one.
   */
  neighbours(id: string): string[] {
    const byLabel = new Map<string, string[]>();
    for (const { edge, other, outgoing } of this.connections(id)) {
      const key = `${outgoing ? "→" : "←"}${edge.label}`;
      if (!byLabel.has(key)) byLabel.set(key, []);
      const list = byLabel.get(key)!;
      if (!list.includes(other.id)) list.push(other.id);
    }
    const queues = [...byLabel.values()];
    const order: string[] = [];
    const placed = new Set<string>();
    while (queues.some((queue) => queue.length)) {
      for (const queue of queues) {
        const next = queue.shift();
        if (next && !placed.has(next)) {
          placed.add(next);
          order.push(next);
        }
      }
    }
    return order;
  }

  /** A node and at most `limit` of its neighbours. */
  around(id: string, limit: number): Set<string> {
    return new Set([id, ...this.neighbours(id).slice(0, limit)]);
  }

  /** The law (or judgment, or guideline) a provision is part of. */
  partOf(id: string): string | undefined {
    return this.nodes.get(id)?.law ?? this.parent.get(id);
  }

  /** The law a node belongs to: itself for a law, judgment or guideline; its law for a provision. */
  lawOf(id: string): { id: string; name: LawName } | undefined {
    const lawId = this.laws[id] ? id : this.partOf(id);
    const name = lawId ? this.laws[lawId] : undefined;
    return lawId && name ? { id: lawId, name } : undefined;
  }

  /**
   * Laws that two or more of these provisions are part of but that are not among them: shown as
   * context, so a view makes clear when its provisions come from the same law.
   */
  sharedParents(ids: Iterable<string>): string[] {
    const present = new Set(ids);
    const children = new Map<string, number>();
    for (const id of present) {
      const parent = this.partOf(id);
      if (parent && !present.has(parent)) children.set(parent, (children.get(parent) ?? 0) + 1);
    }
    return [...children].filter(([, count]) => count >= 2).map(([parent]) => parent);
  }

  /** The ids plus the laws two or more of them share. */
  withParents(ids: Iterable<string>): Set<string> {
    const present = new Set(ids);
    return new Set([...present, ...this.sharedParents(present)]);
  }
}
