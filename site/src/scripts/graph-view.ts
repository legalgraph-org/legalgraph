// Interactive graph (Cytoscape.js) over /graph-data.json: countries, acts, provisions, rules,
// disclosure types, information items and concepts, and the relations between them. Views start
// small, like the Neo4j browser: one node and some of its neighbours, and grow as you expand nodes.
import cytoscape, { type Core, type ElementDefinition, type NodeSingular } from "cytoscape";

import { NODE_COLORS, NODE_SHAPES, SMALL_NODE_TYPES, curie, iri, pagePath, turtlePath } from "../lib/links";

export interface GraphNode {
  id: string;
  label: string;
  title: string;
  type: string;
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

/** The whole graph in memory, with an index of each node's edges. */
export class GraphData {
  readonly nodes: Map<string, GraphNode>;
  private readonly adjacent = new Map<string, GraphEdge[]>();

  constructor(
    nodes: GraphNode[],
    readonly edges: GraphEdge[],
    readonly laws: Record<string, LawName> = {},
  ) {
    this.nodes = new Map(nodes.map((node) => [node.id, node]));
    for (const edge of edges) {
      for (const end of [edge.source, edge.target]) {
        if (!this.adjacent.has(end)) this.adjacent.set(end, []);
        this.adjacent.get(end)!.push(edge);
      }
    }
  }

  connections(id: string): Connection[] {
    return (this.adjacent.get(id) ?? [])
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
    while (queues.some((queue) => queue.length)) {
      for (const queue of queues) {
        const next = queue.shift();
        if (next && !order.includes(next)) order.push(next);
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
    return this.connections(id).find(({ edge, outgoing }) => outgoing && edge.label === "part of")?.other.id;
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
}

let loading: Promise<GraphData> | undefined;

/** Fetches the graph once per page; every view on the page shares it. */
export function loadGraphData(): Promise<GraphData> {
  loading ??= fetch("/graph-data.json")
    .then((response) => {
      if (!response.ok) throw new Error(`/graph-data.json: ${response.status}`);
      return response.json() as Promise<{ nodes: GraphNode[]; edges: GraphEdge[]; laws: Record<string, LawName> }>;
    })
    .then((data) => new GraphData(data.nodes, data.edges, data.laws));
  return loading;
}

let loadingProperties: Promise<Record<string, [string, string][]>> | undefined;

/** The plain properties of every node (/graph-properties.json), fetched the first time they are needed. */
export function loadProperties(): Promise<Record<string, [string, string][]>> {
  loadingProperties ??= fetch("/graph-properties.json").then((response) => {
    if (!response.ok) throw new Error(`/graph-properties.json: ${response.status}`);
    return response.json() as Promise<Record<string, [string, string][]>>;
  });
  return loadingProperties;
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
  const edges = data.edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .map((edge) => ({ group: "edges" as const, data: { id: `${edge.source}|${edge.label}|${edge.target}`, ...edge } }));
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
  return new Set([...ids, ...data.sharedParents(ids)]);
}

/**
 * Brings in the laws that provisions in the view now share, each placed among its provisions.
 * Returns the nodes added.
 */
export function addSharedParents(cy: Core, data: GraphData): string[] {
  const present = new Set(cy.nodes().map((node) => node.id()));
  const parents = data.sharedParents(present);
  if (parents.length === 0) return [];
  const added = elements(data, new Set([...present, ...parents]), new Set(parents)).filter((element) =>
    element.group === "nodes" ? !present.has(element.data.id!) : cy.getElementById(element.data.id!).empty(),
  );
  for (const parent of parents) {
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
  return parents;
}

/**
 * Trims the view to a node and its neighbours in the view, with the relations among them. The only
 * other nodes kept are interim ones that tie them together: a law that two or more of them are part
 * of (shown as context if it was not in the view). Nothing new is brought in otherwise; the kept
 * nodes are arranged around the node. Returns how many nodes were removed.
 */
export function trimTo(cy: Core, data: GraphData, id: string): number {
  const node = cy.getElementById(id);
  if (node.empty()) return 0;
  const near = node.closedNeighborhood().nodes();
  const shared = new Set(data.sharedParents(near.map((n) => n.id())));
  const removed = cy.nodes().not(near).filter((other) => !shared.has(other.id()));
  const count = removed.length;
  removed.remove();
  addSharedParents(cy, data);
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

/** Replaces the view with every jurisdiction (see jurisdictionIds). */
export function showJurisdictions(cy: Core, data: GraphData): void {
  cy.elements().remove();
  // Every EU member is in the EEA too; drawing both links pulls the two hubs into one. Here an EU
  // member hangs on the EU only, and the EEA keeps the members that are not in the EU.
  const inEu = new Set(data.edges.filter((e) => e.label === "member of" && e.target === "EU").map((e) => e.source));
  cy.add(
    elements(data, jurisdictionIds(data)).filter(
      (element) => !(element.group === "edges" && element.data.target === "EEA" && inEu.has(element.data.source as string)),
    ),
  );
  cy.nodes().removeClass("focus");
  cy.layout(layoutFor({ ids: new Set() })).run();
  cy.fit(undefined, 30);
}

/** Replaces the view with a node and at most `limit` of its neighbours. */
export function focusOn(cy: Core, data: GraphData, id: string, limit: number): void {
  cy.elements().remove();
  const ids = data.around(id, limit);
  cy.add(elements(data, withParents(data, ids), new Set(data.sharedParents(ids))));
  cy.nodes().removeClass("focus");
  cy.getElementById(id).addClass("focus");
  cy.layout(focusLayout(id)).run();
  cy.fit(undefined, 30);
}

/** How many of a node's neighbours are not in the view yet. */
export function hiddenNeighbours(cy: Core, data: GraphData, id: string): number {
  return data.neighbours(id).filter((other) => cy.getElementById(other).empty()).length;
}

/**
 * Adds up to `limit` of a node's neighbours that are not in the view yet, placed in a ring around
 * it on the side away from the rest of the view. The nodes already there keep their places, so
 * the picture grows instead of being rearranged. Returns how many were added.
 */
export function expand(cy: Core, data: GraphData, id: string, limit: number): number {
  const node = cy.getElementById(id);
  if (node.empty()) return 0;
  const fresh = data.neighbours(id).filter((other) => cy.getElementById(other).empty()).slice(0, limit);
  if (fresh.length === 0) return 0;
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
  addSharedParents(cy, data);
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
