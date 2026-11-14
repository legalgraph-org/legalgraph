/**
 * Renders an official law page that builds its text with JavaScript and prints the resulting HTML, for
 * `legalgraph sources fetch` (source.yaml `fetch: rendered`), which then cuts the law text out with the
 * original's `selector`, as for html-fragment.
 *
 *   bun tools/render/render.ts <url> [--wait <css selector>] [--timeout <ms>]
 *
 * Headless Chromium (Playwright, pinned in package.json; `bun run install-browser` once per host).
 * With --wait it waits for the element holding the law text; without, for the network to settle.
 * Portals that keep connections open (analytics, long polling) never settle, so name the element.
 */
import { chromium } from "playwright";

const [url, ...rest] = process.argv.slice(2);
const option = (name: string) => {
  const at = rest.indexOf(name);
  return at >= 0 ? rest[at + 1] : undefined;
};
if (!url) {
  console.error("usage: bun tools/render/render.ts <url> [--wait <selector>] [--timeout <ms>]");
  process.exit(2);
}
const timeout = Number(option("--timeout") ?? 60_000);
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ userAgent: "legalgraph (+https://legalgraph.org) Chromium" });
  const wait = option("--wait");
  const response = await page.goto(url, { waitUntil: wait ? "domcontentloaded" : "networkidle", timeout });
  // A portal's refusal (a WAF's 403 page) is not the law text: fail rather than store it.
  if (response && !response.ok()) {
    console.error(`${url} answered HTTP ${response.status()}`);
    process.exitCode = 1;
  } else {
    if (wait) await page.waitForSelector(wait, { timeout });
    process.stdout.write(await page.content());
  }
} finally {
  await browser.close();
}
