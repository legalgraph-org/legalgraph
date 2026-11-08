/** A table of contents read from rendered HTML: h2 entries, each with the h3 entries under it. */
export interface TocEntry {
  id: string;
  text: string;
}

export interface TocGroup extends TocEntry {
  children: TocEntry[];
}

const HEADING = /<h([23])(\s[^>]*)?>([\s\S]*?)<\/h\1>/g;
const ID = /\sid="([^"]*)"/;
const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

/** A heading's text: tags dropped, entities decoded, whitespace collapsed. */
function textOf(html: string): string {
  return html
    .replace(/<[^>]*>/g, "")
    .replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (entity, name: string) => {
      if (name[0] === "#") {
        const code = name[1] === "x" || name[1] === "X" ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10);
        return String.fromCodePoint(code);
      }
      return ENTITIES[name.toLowerCase()] ?? entity;
    })
    .replace(/\s+/g, " ")
    .trim();
}

/** As Markdown headings are slugged (github-slugger): lowercase, punctuation dropped, spaces to dashes. */
function slugOf(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s/g, "-");
}

/**
 * The h2 and h3 headings of `html`, and the same HTML with an id on every one of them. Markdown
 * headings keep the ids they have; hand-written ones get a slug of their text, unique on the page.
 * An h3 before the first h2 is an entry of its own.
 */
export function tableOfContents(html: string): { html: string; groups: TocGroup[] } {
  const taken = new Set([...html.matchAll(/\sid="([^"]*)"/g)].map((match) => match[1]));
  const groups: TocGroup[] = [];
  const withIds = html.replace(HEADING, (heading, depth: string, attributes = "", inner: string) => {
    const text = textOf(inner);
    let id = ID.exec(attributes)?.[1];
    if (!id) {
      const base = slugOf(text) || "section";
      id = base;
      for (let n = 1; taken.has(id); n += 1) id = `${base}-${n}`;
      taken.add(id);
      heading = `<h${depth} id="${id}"${attributes}>${inner}</h${depth}>`;
    }
    const last = groups.at(-1);
    if (depth === "3" && last) {
      last.children.push({ id, text });
    } else {
      groups.push({ id, text, children: [] });
    }
    return heading;
  });
  return { html: withIds, groups };
}
