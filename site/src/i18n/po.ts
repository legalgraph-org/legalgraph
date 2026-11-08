import { readFileSync } from "node:fs";

import { po } from "gettext-parser";

import { messageKey } from "./message";

export interface PoEntry {
  msgid: string;
  context?: string;
  /** msgstr, or msgstr[0] for plural entries. */
  msgstr: string;
  plural?: string;
  pluralForms: readonly string[];
  fuzzy: boolean;
  references: readonly string[];
}

export interface PoFile {
  headers: Readonly<Record<string, string>>;
  entries: readonly PoEntry[];
  obsoleteCount: number;
}

export function parsePo(source: string | Buffer): PoFile {
  const parsed = po.parse(source);
  const entries: PoEntry[] = [];
  for (const [context, messages] of Object.entries(parsed.translations)) {
    for (const [msgid, message] of Object.entries(messages)) {
      if (msgid === "") {
        continue; // the header entry
      }
      entries.push({
        msgid,
        ...(context ? { context } : {}),
        msgstr: message.msgstr[0] ?? "",
        ...(message.msgid_plural ? { plural: message.msgid_plural } : {}),
        pluralForms: message.msgstr,
        fuzzy: (message.comments?.flag ?? "").split(",").some((flag) => flag.trim() === "fuzzy"),
        references: (message.comments?.reference ?? "").split(/\s+/).filter(Boolean),
      });
    }
  }
  const obsoleteCount = Object.values(parsed.obsolete ?? {}).reduce(
    (count, messages) => count + Object.keys(messages).length,
    0,
  );
  return { headers: parsed.headers, entries, obsoleteCount };
}

export function readPo(path: string): PoFile {
  return parsePo(readFileSync(path));
}

/**
 * The translations a build may use: translated and not fuzzy. A fuzzy entry is a translation of
 * the *previous* English text (msgmerge marks it when the msgid changed), so it counts as missing.
 */
export function usableTranslations(file: PoFile): ReadonlyMap<string, string> {
  const map = new Map<string, string>();
  for (const entry of file.entries) {
    if (!entry.fuzzy && entry.msgstr !== "") {
      map.set(messageKey(entry.msgid, entry.context), entry.msgstr);
    }
  }
  return map;
}
