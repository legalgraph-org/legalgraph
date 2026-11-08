/**
 * Rich-text messages mark spans with numbered tags, e.g.
 *   "Details can be found in our <0>Privacy Policy</0> and <1>Terms & Conditions</1>."
 * The tags carry no attributes and do not nest; <T> (T.astro) wraps each span in the element the
 * page passes for that index. Translations are never rendered with set:html.
 */
export type RichTextPart =
  { kind: "text"; text: string } | { kind: "tag"; index: number; text: string };

export type RichTag =
  { kind: "link"; href: string; newTab?: boolean } | { kind: "strong" } | { kind: "em" } | { kind: "code" };

export function parseRichText(message: string): RichTextPart[] {
  const parts: RichTextPart[] = [];
  const pattern = /<(\d+)>([^<]*)<\/\1>/g;
  let cursor = 0;
  for (const match of message.matchAll(pattern)) {
    const start = match.index;
    if (start > cursor) {
      parts.push({ kind: "text", text: message.slice(cursor, start) });
    }
    parts.push({ kind: "tag", index: Number(match[1]), text: match[2] ?? "" });
    cursor = start + match[0].length;
  }
  if (cursor < message.length) {
    parts.push({ kind: "text", text: message.slice(cursor) });
  }
  const leftover = parts.find((part) => part.kind === "text" && /<\/?\d+>/.test(part.text));
  if (leftover) {
    throw new Error(
      `Malformed rich-text message (unbalanced, nested or attributed tag): ${JSON.stringify(message)}`,
    );
  }
  return parts;
}
