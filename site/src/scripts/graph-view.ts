// Interactive graph (Cytoscape.js): countries, acts, provisions, rules, disclosure types, information
// items and concepts, and the relations between them. Views start small, like the Neo4j browser: one
// node and some of its neighbours, and grow as you expand nodes.
//
// The graph view does not download the whole graph: it starts from /graph-index.json (every node,
// without edges) and fetches a node's edges and properties (/graph-node/<id>.json) when it first shows
// or selects that node (LazyGraph). Every node in a view is loaded, so the view knows every edge
// between its nodes. A page's mini graph gets its neighbourhood with the page (MiniGraph.astro).
import cytoscape, { type Core, type ElementDefinition, type NodeSingular } from "cytoscape";

import { GraphData, edgeKey, type GraphEdge, type GraphNode, type LawName } from "../lib/graph-model";
import { NODE_COLORS, NODE_SHAPES, SMALL_NODE_TYPES, curie, iri, pagePath, turtlePath } from "../lib/links";

export { GraphData, type Connection, type GraphEdge, type GraphNode, type LawName } from "../lib/graph-model";

export type Property = [string, string];

/** The graph as the graph view knows it: every node, and the edges and properties of the nodes loaded so far. */
export class LazyGraph extends GraphData {
  private readonly loading = new Map<string, Promise<void>>();
  private readonly props = new Map<string, Property[]>();

  constructor(
    nodes: (Omit<GraphNode, "title"> & { title?: string })[],
    edges: GraphEdge[],
    laws: Record<string, LawName>,
    /** Other names of nodes, for the search (lib/graph-search.ts). */
    readonly terms: Record<string, string[]>,
  ) {
    super(
      nodes.map((node) => ({ ...node, title: node.title ?? node.label })),
      edges,
      laws,
    );
  }

  /** Fetches the nodes not loaded yet, all at once; a failed fetch is tried again next time. */
  override async ensure(ids: Iterable<string>): Promise<void> {
    await Promise.all([...new Set(ids)].filter((id) => this.nodes.has(id)).map((id) => this.load(id)));
  }

  /** A loaded node's properties. */
  properties(id: string): Property[] {
    return this.props.get(id) ?? [];
  }

  private load(id: string): Promise<void> {
    let pending = this.loading.get(id);
    if (!pending) {
      const url = `/graph-node/${encodeURIComponent(id)}.json`;
      pending = fetch(url)
        .then((response) => {
          if (!response.ok) throw new Error(`${url}: ${response.status}`);
          return response.json() as Promise<{ edges: [string, string, 0 | 1][]; properties: Property[] }>;
        })
        .then((shard) => {
          this.addEdges(
            shard.edges.map(([label, other, outgoing]) =>
              outgoing ? { source: id, target: other, label } : { source: other, target: id, label },
            ),
          );
          this.props.set(id, shard.properties);
        })
        .catch((error: unknown) => {
          this.loading.delete(id);
          throw error;
        });
      this.loading.set(id, pending);
    }
    return pending;
  }
}

let loading: Promise<LazyGraph> | undefined;

/** Fetches the graph's index once per page (see the top of this file). */
export function loadGraphIndex(): Promise<LazyGraph> {
  loading ??= fetch("/graph-index.json")
    .then((response) => {
      if (!response.ok) throw new Error(`/graph-index.json: ${response.status}`);
      return response.json() as Promise<{
        nodes: (Omit<GraphNode, "title"> & { title?: string })[];
        edges: GraphEdge[];
        laws: Record<string, LawName>;
        terms: Record<string, string[]>;
      }>;
    })
    .then((index) => new LazyGraph(index.nodes, index.edges, index.laws, index.terms));
  return loading;
}

/** A provision's text for the reading panel (/graph-text/<id>.json). */
export interface ProvisionText {
  citation: string;
  original: { lang: string; text: string; official: boolean; sourceUrl: string | null; retrievedOn: string | null };
  counterpart: {
    kind: "translation" | "version";
    lang: string;
    text: string;
    official?: boolean;
    method?: string;
    status?: string;
  } | null;
}

const texts = new Map<string, Promise<ProvisionText | undefined>>();

/** A provision's text, fetched once; undefined when it has none. */
export function loadText(id: string): Promise<ProvisionText | undefined> {
  if (!texts.has(id)) {
    texts.set(
      id,
      fetch(`/graph-text/${encodeURIComponent(id)}.json`)
        .then((response) => (response.ok ? (response.json() as Promise<ProvisionText>) : undefined))
        .catch(() => undefined),
    );
  }
  return texts.get(id)!;
}

export const TYPE_LABELS: Record<string, string> = {
  organisation: "EU / EEA",
  country: "Country",
  act: "Legal act",
  provision: "Provision",
  disclosure: "Disclosure type",
  item: "Information item",
  concept: "Legal concept",
  decision: "Court or authority decision",
  rule: "Rule (obligation)",
  guidance: "Guidance",
};

const VOCAB_TYPES = new Set(["item", "disclosure", "concept", "condition", "action", "role"]);
const space = (node: GraphNode) => (VOCAB_TYPES.has(node.type) ? "vocab" : "id");
export const nodeHref = (node: GraphNode) => pagePath(space(node), node.id);
export const nodeTurtle = (node: GraphNode) => turtlePath(space(node), node.id);
export const nodeCurie = (node: GraphNode) => curie(space(node), node.id);
export const nodeIri = (node: GraphNode) => iri(space(node), node.id);
export const nodeColor = (node: GraphNode) => NODE_COLORS[node.type] ?? "currentColor";

/** The view's elements; `context` nodes (shared laws) are drawn fainter, with a dashed outline. */
function elements(data: GraphData, ids: Set<string>, context: ReadonlySet<string> = new Set()): ElementDefinition[] {
  const nodes = [...ids]
    .filter((id) => data.nodes.has(id))
    .map((id) => ({ group: "nodes" as const, data: { ...data.nodes.get(id)! }, classes: context.has(id) ? "context" : "" }));
  const edges = data.edgesAmong(ids).map((edge) => ({ group: "edges" as const, data: { id: edgeKey(edge), ...edge } }));
  return [...nodes, ...edges];
}

export interface GraphOptions {
  data: GraphData;
  ids: Set<string>;
  focus?: string;
  compact?: boolean;
  /** Fixed positions for every node (a drawn diagram rather than a computed layout). */
  positions?: Record<string, { x: number; y: number }>;
  /** Show every label in full (wrapped) and name every edge, for a small diagram meant to be read. */
  annotated?: boolean;
  onSelect?: (node: GraphNode | undefined) => void;
}

/**
 * A theme role (tokens.css) as an rgb() colour Cytoscape can draw: the variable is resolved where the
 * graph sits, so the graph follows the theme around it. Canvas normalises any CSS colour
 * (color-mix, oklab) to RGB.
 */
function themeColor(container: HTMLElement, role: string): string {
  const probe = document.createElement("span");
  probe.style.color = `var(${role})`;
  container.append(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return color;
  context.fillStyle = color;
  context.fillRect(0, 0, 1, 1);
  const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
  return `rgb(${r}, ${g}, ${b})`;
}

export function mountGraph(container: HTMLElement, options: GraphOptions): Core {
  const [text, text2, background, border, borderStrong, primary] = [
    "--text",
    "--text-2",
    "--background",
    "--border",
    "--border-strong",
    "--primary",
  ].map((role) => themeColor(container, role));
  const cy = cytoscape({
    container,
    // A drawn diagram shows exactly its nodes; a computed view adds the laws its provisions share.
    elements: options.positions
      ? elements(options.data, options.ids)
      : elements(options.data, withParents(options.data, options.ids), new Set(options.data.sharedParents(options.ids))),
    // Small neighbourhoods would otherwise be zoomed in until labels collide.
    maxZoom: options.compact ? 1.3 : 2.5,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (node: NodeSingular) => NODE_COLORS[node.data("type")] ?? text2,
          label: "data(label)",
          color: text,
          "font-size": options.annotated ? 12 : options.compact ? 9 : 10,
          // Labels appear once zoomed in far enough to read them, so the full graph is not a wall of text.
          "min-zoomed-font-size": 7,
          "text-valign": "bottom",
          "text-margin-y": 3,
          "text-wrap": options.annotated ? "wrap" : "ellipsis",
          "text-max-width": options.annotated ? "130px" : "110px",
          "text-background-color": background,
          "text-background-opacity": 0.8,
          "text-background-padding": "1px",
          shape: (node: NodeSingular) => NODE_SHAPES[node.data("type")] ?? "ellipse",
          width: (node: NodeSingular) => (SMALL_NODE_TYPES.has(node.data("type")) ? 14 : 22),
          height: (node: NodeSingular) => (SMALL_NODE_TYPES.has(node.data("type")) ? 14 : 22),
        },
      },
      {
        selector: "edge",
        style: {
          width: 1,
          "line-color": border,
          "target-arrow-color": borderStrong,
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.7,
          "curve-style": "bezier",
        },
      },
      ...(options.annotated
        ? [
            {
              selector: "edge",
              style: {
                label: "data(label)",
                "font-size": 10,
                color: text2,
                "text-rotation": "autorotate" as const,
                "text-background-color": background,
                "text-background-opacity": 1,
                "text-background-padding": "1px",
              },
            },
          ]
        : []),
      { selector: "edge.highlight", style: { "line-color": primary, "target-arrow-color": primary } },
      {
        // Edge names appear on hover only, so a busy neighbourhood stays readable.
        selector: "edge:selected, edge.hover",
        style: {
          label: "data(label)",
          "font-size": 9,
          color: text,
          "line-color": primary,
          "target-arrow-color": primary,
          "text-background-color": background,
          "text-background-opacity": 1,
          "text-background-padding": "2px",
          "z-index": 10,
        },
      },
      {
        selector: "node.context",
        style: { opacity: 0.8, "border-width": 2, "border-style": "dashed", "border-color": text2, "background-opacity": 0.55 },
      },
      { selector: "node:selected", style: { "border-width": 3, "border-color": text, "border-style": "solid" } },
      { selector: "node.focus", style: { "border-width": 3, "border-color": primary } },
      { selector: ".hidden", style: { display: "none" } },
    ],
    layout: layoutFor(options),
  });

  if (options.focus) cy.getElementById(options.focus).addClass("focus");
  cy.on("mouseover", "edge", (event) => event.target.addClass("hover"));
  cy.on("mouseout", "edge", (event) => event.target.removeClass("hover"));
  cy.on("mouseover", "node", (event) => event.target.connectedEdges().addClass("hover"));
  cy.on("mouseout", "node", (event) => event.target.connectedEdges().removeClass("hover"));
  cy.on("select", "node", (event) => {
    cy.edges().removeClass("highlight");
    event.target.connectedEdges().addClass("highlight");
    options.onSelect?.(options.data.nodes.get(event.target.id()));
  });
  cy.on("unselect", "node", () => {
    cy.edges().removeClass("highlight");
    options.onSelect?.(undefined);
  });
  return cy;
}

/** A focused view: the focus in the middle, its neighbours in rings around it. */
export function focusLayout(focus?: string, animate = false) {
  return {
    name: "concentric" as const,
    concentric: (node: NodeSingular) => (node.id() === focus ? 2 : 1),
    levelWidth: () => 1,
    minNodeSpacing: 40,
    animate,
    animationDuration: 300,
    padding: 30,
  };
}

function layoutFor(options: { focus?: string; ids: Set<string>; positions?: GraphOptions["positions"] }) {
  if (options.positions) {
    const positions = options.positions;
    return { name: "preset" as const, positions: (node: NodeSingular) => positions[node.id()] ?? { x: 0, y: 0 }, padding: 24 };
  }
  return options.focus
    ? focusLayout(options.focus)
    : { name: "cose", animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 60, padding: 20 };
}

/** The ids plus the laws two or more of them share. */
function withParents(data: GraphData, ids: Set<string>): Set<string> {
  return data.withParents(ids);
}

/**
 * Brings in the laws that provisions in the view now share, each placed among its provisions.
 * Returns the nodes added.
 */
export async function addSharedParents(cy: Core, data: GraphData): Promise<string[]> {
  const parents = data.sharedParents(cy.nodes().map((node) => node.id()));
  if (parents.length === 0) return [];
  await data.ensure(parents);
  // The view may have changed while the laws were fetched.
  const present = new Set(cy.nodes().map((node) => node.id()));
  const fresh = parents.filter((parent) => !present.has(parent));
  if (fresh.length === 0) return [];
  const added = elements(data, new Set([...present, ...fresh]), new Set(fresh)).filter((element) =>
    element.group === "nodes" ? !present.has(element.data.id!) : cy.getElementById(element.data.id!).empty(),
  );
  for (const parent of fresh) {
    const children = cy.nodes().filter((node) => data.partOf(node.id()) === parent);
    let x = 0;
    let y = 0;
    children.forEach((child: NodeSingular) => {
      x += child.position("x");
      y += child.position("y");
    });
    const element = added.find((e) => e.group === "nodes" && e.data.id === parent);
    if (element && children.length) element.position = { x: x / children.length + 30, y: y / children.length - 30 };
  }
  cy.add(added);
  return fresh;
}

/**
 * Trims the view to a node and its neighbours in the view, with the relations among them. The only
 * other nodes kept are interim ones that tie them together: a law that two or more of them are part
 * of (shown as context if it was not in the view). Nothing new is brought in otherwise; the kept
 * nodes are arranged around the node. Returns how many nodes were removed.
 */
export async function trimTo(cy: Core, data: GraphData, id: string): Promise<number> {
  const node = cy.getElementById(id);
  if (node.empty()) return 0;
  const near = node.closedNeighborhood().nodes();
  const shared = new Set(data.sharedParents(near.map((n) => n.id())));
  const removed = cy.nodes().not(near).filter((other) => !shared.has(other.id()));
  const count = removed.length;
  removed.remove();
  await addSharedParents(cy, data);
  cy.nodes().removeClass("focus");
  node.addClass("focus");
  cy.layout(focusLayout(id, true)).run();
  return count;
}

/**
 * The starting view: every jurisdiction, with the EU and the EEA as hubs of their members and states
 * or provinces next to their country. No country is put in the middle; everything else is a click away.
 */
export function jurisdictionIds(data: GraphData): Set<string> {
  return new Set([...data.nodes.values()].filter((node) => node.type === "country" || node.type === "organisation").map((node) => node.id));
}

/** Replaces the view with every jurisdiction (see jurisdictionIds; their edges come with the index). */
export function showJurisdictions(cy: Core, data: GraphData): void {
  cy.elements().remove();
  const ids = jurisdictionIds(data);
  // Every EU member is in the EEA too; drawing both links pulls the two hubs into one. Here an EU
  // member hangs on the EU only, and the EEA keeps the members that are not in the EU.
  const inEu = new Set(data.edgesAmong(ids).filter((e) => e.label === "member of" && e.target === "EU").map((e) => e.source));
  cy.add(
    elements(data, ids).filter(
      (element) => !(element.group === "edges" && element.data.target === "EEA" && inEu.has(element.data.source as string)),
    ),
  );
  cy.nodes().removeClass("focus");
  cy.layout(layoutFor({ ids: new Set() })).run();
  cy.fit(undefined, 30);
}

/** Replaces the view with a node and at most `limit` of its neighbours. */
export async function focusOn(cy: Core, data: GraphData, id: string, limit: number): Promise<void> {
  await data.ensure([id]);
  const ids = data.around(id, limit);
  const shown = withParents(data, ids);
  await data.ensure(shown);
  cy.elements().remove();
  cy.add(elements(data, shown, new Set(data.sharedParents(ids))));
  cy.nodes().removeClass("focus");
  cy.getElementById(id).addClass("focus");
  cy.layout(focusLayout(id)).run();
  cy.fit(undefined, 30);
}

/** How many of a node's neighbours are not in the view yet (the node must be loaded). */
export function hiddenNeighbours(cy: Core, data: GraphData, id: string): number {
  return data.neighbours(id).filter((other) => cy.getElementById(other).empty()).length;
}

/**
 * Adds up to `limit` of a node's neighbours that are not in the view yet, placed in a ring around
 * it on the side away from the rest of the view. The nodes already there keep their places, so
 * the picture grows instead of being rearranged. Returns how many were added.
 */
export async function expand(cy: Core, data: GraphData, id: string, limit: number): Promise<number> {
  await data.ensure([id]);
  const candidates = data.neighbours(id).filter((other) => cy.getElementById(other).empty()).slice(0, limit);
  await data.ensure(candidates);
  const node = cy.getElementById(id);
  // The view may have changed while the neighbours were fetched.
  const fresh = candidates.filter((other) => cy.getElementById(other).empty());
  if (node.empty() || fresh.length === 0) return 0;
  const present = new Set(cy.nodes().map((n) => n.id()));
  const center = node.position();
  const others = cy.nodes().not(node);
  // The direction from the middle of the rest of the view towards this node.
  let sumX = 0;
  let sumY = 0;
  others.forEach((other: NodeSingular) => {
    sumX += other.position("x");
    sumY += other.position("y");
  });
  const away = others.length ? Math.atan2(center.y - sumY / others.length, center.x - sumX / others.length) : 0;
  // A ring facing away from the rest (a full one for many nodes), wide enough for its nodes.
  const spread = others.length && fresh.length <= 12 ? Math.PI * 1.2 : Math.PI * 2;
  const radius = Math.max(90, (fresh.length * 46) / spread);
  const added = elements(data, new Set([...present, ...fresh])).filter((element) =>
    element.group === "nodes" ? !present.has(element.data.id!) : cy.getElementById(element.data.id!).empty(),
  );
  fresh.forEach((other, index) => {
    const angle = away - spread / 2 + (spread * (index + 0.5)) / fresh.length;
    const element = added.find((e) => e.group === "nodes" && e.data.id === other);
    if (element) element.position = { x: center.x + radius * Math.cos(angle), y: center.y + radius * Math.sin(angle) };
  });
  const old = cy.nodes();
  cy.add(added);
  await addSharedParents(cy, data);
  // Let only the new nodes settle (no overlaps, short edges); the rest of the view stays where it was.
  old.lock();
  const layout = cy.layout({
    name: "cose",
    randomize: false,
    animate: true,
    animationDuration: 350,
    fit: false,
    nodeRepulsion: () => 12000,
    idealEdgeLength: () => 80,
    numIter: 400,
  });
  layout.one("layoutstop", () => old.unlock());
  layout.run();
  return fresh.length;
}

/**
 * Adds one node next to another (or anywhere), with its edges to the nodes in the view and the laws
 * it now shares with them. Returns false if it is not in the graph.
 */
export async function addNode(cy: Core, data: GraphData, id: string, near?: { x: number; y: number }): Promise<boolean> {
  const node = data.nodes.get(id);
  if (!node) return false;
  await data.ensure([id]);
  if (cy.getElementById(id).nonempty()) return true;
  cy.add({ group: "nodes", data: { ...node }, position: near ? { x: near.x + 80, y: near.y + 40 } : { x: 0, y: 0 } });
  for (const edge of data.edgesOf(id)) {
    const key = edgeKey(edge);
    if (cy.getElementById(edge.source).nonempty() && cy.getElementById(edge.target).nonempty() && cy.getElementById(key).empty()) {
      cy.add({ group: "edges", data: { id: key, ...edge } });
    }
  }
  await addSharedParents(cy, data);
  return true;
}
