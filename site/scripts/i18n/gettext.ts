/**
 * GNU gettext tools (msgmerge, msgattrib) are system binaries, not npm packages. The version is
 * pinned here and checked on every run; CI images must install exactly this version
 *. Dev: `brew install gettext`.
 */
import { spawnSync } from "node:child_process";

export const GETTEXT_VERSION = process.env.GETTEXT_VERSION ?? "1.0";

function run(tool: string, args: readonly string[]): string {
  const result = spawnSync(tool, args, { encoding: "utf8" });
  if (result.error) {
    throw new Error(
      `${tool} is not installed (GNU gettext ${GETTEXT_VERSION}): brew install gettext`,
      {
        cause: result.error,
      },
    );
  }
  if (result.status !== 0) {
    throw new Error(`${tool} ${args.join(" ")} failed:\n${result.stderr}`);
  }
  return result.stdout;
}

export function checkGettextVersion(): void {
  const firstLine = run("msgmerge", ["--version"]).split("\n")[0] ?? "";
  const version = /\)\s+([\d.]+)/.exec(firstLine)?.[1];
  if (version !== GETTEXT_VERSION) {
    throw new Error(
      `GNU gettext ${GETTEXT_VERSION} is pinned, found ${JSON.stringify(firstLine)}. ` +
        "Install the pinned version, or set GETTEXT_VERSION after updating CI.",
    );
  }
}

/** Shared by every msgmerge/msgattrib call so all .po files keep one layout. */
const LAYOUT = ["--no-wrap", "--sort-output"];

/**
 * Merges the template into a translated catalog: changed English text becomes `#, fuzzy`. With a
 * compendium, messages the catalog lacks are filled from it (another site's catalogs).
 */
export function msgmergeUpdate(poPath: string, potPath: string, compendiumPath?: string): void {
  run("msgmerge", [
    "--quiet",
    "--update",
    "--previous",
    "--backup=none",
    ...(compendiumPath ? [`--compendium=${compendiumPath}`] : []),
    ...LAYOUT,
    poPath,
    potPath,
  ]);
}

/** Creates a catalog for the template, pre-filled from an existing catalog (the compendium). */
export function msgmergeFromCompendium(
  outPath: string,
  potPath: string,
  compendiumPath: string,
): void {
  run("msgmerge", [
    "--quiet",
    "--previous",
    `--compendium=${compendiumPath}`,
    ...LAYOUT,
    "-o",
    outPath,
    "/dev/null",
    potPath,
  ]);
}

/**
 * Drops fuzzy entries before a seeding merge: msgmerge keeps a catalog's own fuzzy guess over an
 * exact translation in the compendium.
 */
export function dropFuzzy(poPath: string): void {
  run("msgattrib", ["--no-fuzzy", ...LAYOUT, "-o", poPath, poPath]);
}

/** Drops obsolete `#~` entries. */
export function pruneObsolete(poPath: string): void {
  run("msgattrib", ["--no-obsolete", ...LAYOUT, "-o", poPath, poPath]);
}
