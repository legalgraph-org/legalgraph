import { readdirSync } from "node:fs";
import { join, relative } from "node:path";

/** Every .astro and .ts file under src/, as project-relative paths (used in `#:` references). */
export function translatableSources(root: string): string[] {
  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        return walk(path);
      }
      return /\.(astro|ts)$/.test(entry.name) && !entry.name.endsWith(".d.ts") ? [path] : [];
    });
  return walk(join(root, "src"))
    .map((path) => relative(root, path))
    .sort();
}
