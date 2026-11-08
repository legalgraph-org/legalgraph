import { po, type GetTextTranslation } from "gettext-parser";

import type { ExtractedMessage } from "./extractor";

interface PotEntry {
  msgid: string;
  context?: string;
  references: string[];
}

/** Groups extracted calls into unique (context, msgid) entries with every reference. */
export function collectEntries(messages: readonly ExtractedMessage[]): PotEntry[] {
  const byKey = new Map<string, PotEntry>();
  for (const message of messages) {
    const key = `${message.context ?? ""}\u0004${message.msgid}`;
    const entry = byKey.get(key) ?? {
      msgid: message.msgid,
      ...(message.context ? { context: message.context } : {}),
      references: [],
    };
    if (!entry.references.includes(message.reference)) {
      entry.references.push(message.reference);
    }
    byKey.set(key, entry);
  }
  return [...byKey.values()].sort((a, b) => a.msgid.localeCompare(b.msgid, "en"));
}

export function compilePot(entries: readonly PotEntry[]): Buffer {
  const translations: Record<string, Record<string, GetTextTranslation>> = { "": {} };
  for (const entry of entries) {
    const context = entry.context ?? "";
    translations[context] ??= {};
    translations[context][entry.msgid] = {
      msgid: entry.msgid,
      ...(entry.context ? { msgctxt: entry.context } : {}),
      msgstr: [""],
      comments: { reference: entry.references.sort().join(" ") },
    };
  }
  return po.compile(
    {
      charset: "utf-8",
      headers: {
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "X-Generator": "legalgraph site/scripts/i18n/extract.ts",
      },
      translations,
    },
    { foldLength: 0 },
  );
}
