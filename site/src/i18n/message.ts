/**
 * Message rules shared by the runtime lookup (t.ts), the extractor and the CI check, so the three
 * always agree on what a msgid is.
 */

/** gettext separates msgctxt and msgid with EOT in compiled catalogs; we use it as the map key. */
const CONTEXT_SEPARATOR = "\u0004";

/** Runs of whitespace collapse to one space, so source formatting never creates a new msgid. */
export function normalizeMsgid(msgid: string): string {
  return msgid.replace(/\s+/g, " ").trim();
}

export function messageKey(msgid: string, context?: string): string {
  const normalized = normalizeMsgid(msgid);
  return context ? `${context}${CONTEXT_SEPARATOR}${normalized}` : normalized;
}

/** `{name}` placeholders, sorted and de-duplicated. Plain gettext text, not ICU. */
export function placeholdersOf(message: string): string[] {
  return [
    ...new Set([...message.matchAll(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g)].map((m) => m[1] ?? "")),
  ].sort();
}

/** `<n>` tag indexes used by rich-text messages (see rich-text.ts), sorted and de-duplicated. */
export function tagsOf(message: string): number[] {
  return [...new Set([...message.matchAll(/<(\d+)>/g)].map((m) => Number(m[1])))].sort(
    (a, b) => a - b,
  );
}

export type MessageValues = Readonly<Record<string, string | number>>;

export function interpolate(message: string, values: MessageValues | undefined): string {
  return message.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (_match, name: string) => {
    const value = values?.[name];
    if (value === undefined) {
      throw new Error(`Message ${JSON.stringify(message)} needs a value for {${name}}`);
    }
    return String(value);
  });
}

/** Messages longer than this belong in a content collection, not in .po. */
export const MAX_MESSAGE_LENGTH = 300;
