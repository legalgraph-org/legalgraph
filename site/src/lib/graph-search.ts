// Finding nodes by any of their names, for the graph view's search box. A node is found by its label
// and title and by the other names the graph and the glossary give it (`terms`, from
// /graph-index.json): a law by its abbreviation in any language (DSGVO for the GDPR), its full titles,
// its official number; a concept by its labels in every language. A provision is also found by the
// names of its law, so "Art 6 DSGVO" finds Art. 6 GDPR.
//
// A node is also found by its identifier (DE-DDG-s5-1), typed whole or its beginning, with a hyphen
// in it (so "de" is a word, not every German node). The numbers in an identifier do not count as
// words, so "6" does not find Regulation 2016/679.
//
// Every word typed must start a word of a name (case, accents and punctuation do not count; a number
// must match whole, except the last one while it is being typed). Exact names come first, then
// names that start with what was typed, then the rest, laws and countries before their provisions.

export interface SearchNode {
  id: string;
  label: string;
  title: string;
  type: string;
  law?: string;
}

export interface SearchHit {
  node: SearchNode;
  score: number;
  /** The other name that matched (DSGVO for the GDPR), when it is not the node's label or title. */
  alias?: string;
}

/** Lower case, without accents; ß as ss. */
export function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/ß/g, "ss");
}

/** The words of a text, folded: "§ 5 Abs. 1 DDG" -> ["5", "abs", "1", "ddg"]. */
export function words(text: string): string[] {
  return fold(text)
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean);
}

// Kinds that are hubs of the graph come first among equally good matches.
const TYPE_WEIGHT: Record<string, number> = {
  organisation: 6,
  country: 6,
  act: 6,
  decision: 3,
  guidance: 3,
  concept: 3,
  disclosure: 3,
  item: 3,
  rule: 1,
};

interface Entry {
  node: SearchNode;
  id: string;
  /** Each name as its words joined by one space, with the name as written. */
  names: { phrase: string; text: string; alias: boolean }[];
  words: Set<string>;
}

const NUMBER = /^\p{N}+$/u;

function wordScore(query: string, last: boolean, candidates: Iterable<string>): number {
  let best = 0;
  for (const word of candidates) {
    if (word === query) return 3;
    if (word.startsWith(query) && (last || !NUMBER.test(query))) best = 2;
  }
  return best;
}

export class GraphSearch {
  private readonly entries: Entry[];
  private readonly lawWords = new Map<string, Set<string>>();

  constructor(nodes: Iterable<SearchNode>, terms: Readonly<Record<string, readonly string[]>> = {}) {
    this.entries = [...nodes].map((node) => {
      const names: Entry["names"] = [];
      const add = (text: string, alias: boolean) => {
        const phrase = words(text).join(" ");
        if (phrase && !names.some((name) => name.phrase === phrase)) names.push({ phrase, text, alias });
      };
      for (const text of [node.label, node.title]) add(text, false);
      for (const text of terms[node.id] ?? []) add(text, true);
      return { node, id: fold(node.id), names, words: new Set(names.flatMap((name) => name.phrase.split(" "))) };
    });
    for (const entry of this.entries) this.lawWords.set(entry.node.id, entry.words);
  }

  /** The best matches, at most `limit`, and how many nodes match in all. */
  find(query: string, limit = 50): { hits: SearchHit[]; total: number } {
    const typed = words(query);
    if (typed.length === 0) return { hits: [], total: 0 };
    const phrase = typed.join(" ");
    const id = query.includes("-") ? fold(query.trim()) : undefined;
    const hits: SearchHit[] = [];
    for (const entry of this.entries) {
      if (id && entry.id.startsWith(id)) {
        hits.push({ node: entry.node, score: (entry.id === id ? 100 : 40) + (TYPE_WEIGHT[entry.node.type] ?? 0) });
        continue;
      }
      const lawWords = entry.node.law ? this.lawWords.get(entry.node.law) : undefined;
      let score = 0;
      let matched = true;
      for (const [index, word] of typed.entries()) {
        const last = index === typed.length - 1;
        const own = wordScore(word, last, entry.words);
        // A provision's own words count fully, its law's names half.
        const fromLaw = own ? 0 : lawWords ? wordScore(word, last, lawWords) / 2 : 0;
        if (!own && !fromLaw) {
          matched = false;
          break;
        }
        score += own || fromLaw;
      }
      if (!matched) continue;
      let alias: string | undefined;
      let best = 0;
      for (const name of entry.names) {
        const bonus =
          name.phrase === phrase ? 100 : name.phrase.startsWith(phrase) ? 40 : name.phrase.includes(` ${phrase}`) ? 15 : 0;
        if (bonus > best) {
          best = bonus;
          alias = name.alias ? name.text : undefined;
        }
      }
      score += best + (TYPE_WEIGHT[entry.node.type] ?? 0);
      hits.push({ node: entry.node, score, ...(alias ? { alias } : {}) });
    }
    hits.sort(
      (a, b) =>
        b.score - a.score ||
        a.node.label.localeCompare(b.node.label, undefined, { numeric: true, sensitivity: "base" }) ||
        a.node.id.localeCompare(b.node.id),
    );
    return { hits: hits.slice(0, limit), total: hits.length };
  }
}
