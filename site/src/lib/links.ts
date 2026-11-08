// Identifiers and paths. Each resource's page lives at the path of its identifier, so once the
// site runs on the graph's domain, every identifier resolves to its own page (and, with
// `Accept: text/turtle`, to its Turtle; see worker/).
export const ID_BASE = "https://legalgraph.org/id/";
export const VOCAB_BASE = "https://legalgraph.org/vocab/";

export type Space = "id" | "vocab";

export const pagePath = (space: Space, id: string) => `/${space}/${encodeURIComponent(id)}`;
export const turtlePath = (space: Space, id: string) => `${pagePath(space, id)}.ttl`;
// The graph view is a page in every language; the graph's own pages (/id/…) are in English, so they
// link to the English one.
export const graphPath = (focus?: string, locale = "en") =>
  focus ? `/${locale}/graph?focus=${encodeURIComponent(focus)}` : `/${locale}/graph`;
export const iri = (space: Space, id: string) => `${space === "id" ? ID_BASE : VOCAB_BASE}${id}`;
export const curie = (space: Space, id: string) => `${space === "id" ? "lg" : "lgv"}:${id}`;

const languageNames = new Intl.DisplayNames(["en"], { type: "language" });
export const languageName = (code: string) => (code ? (languageNames.of(code) ?? code) : "");

export const STATUS: Record<string, { label: string; tone: string; help: string }> = {
  SourceChecked: {
    label: "Source checked",
    tone: "tone-checked",
    help: "Citation and text compared with the official source. Not a legal review.",
  },
  Draft: {
    label: "Draft",
    tone: "tone-draft",
    help: "Not yet checked: taken from research notes (laws) or not yet reviewed by a person (translations).",
  },
  Reviewed: {
    label: "Reviewed",
    tone: "tone-reviewed",
    help: "A person who reads both languages checked this translation.",
  },
};

export const METHOD: Record<string, string> = {
  MachineTranslation: "Machine translation",
  HumanTranslation: "Human translation",
  OfficialTranslation: "Official translation",
};

/**
 * How each kind of node is drawn: the graph views (Cytoscape shapes) and their legends use these,
 * so a symbol means the same in both. Provisions and items are drawn smaller: there are many.
 */
export type NodeShape = "ellipse" | "round-rectangle" | "tag" | "diamond" | "hexagon" | "star";

export const NODE_SHAPES: Record<string, NodeShape> = {
  organisation: "ellipse",
  country: "ellipse",
  act: "round-rectangle",
  provision: "ellipse",
  disclosure: "diamond",
  item: "ellipse",
  concept: "hexagon",
  decision: "tag",
  rule: "star",
  guidance: "tag",
};

export const SMALL_NODE_TYPES = new Set(["provision", "item"]);

export const NODE_COLORS: Record<string, string> = {
  organisation: "#4338ca",
  country: "#6366f1",
  act: "#0f766e",
  provision: "#0891b2",
  disclosure: "#c2410c",
  item: "#d97706",
  concept: "#7c3aed",
  decision: "#be123c",
  rule: "#15803d",
  guidance: "#9f1239",
};
