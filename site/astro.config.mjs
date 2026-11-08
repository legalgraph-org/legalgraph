import { readdirSync, readFileSync } from "node:fs";
import { rename, writeFile } from "node:fs/promises";

import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

import { unprefixedRedirects } from "./src/lib/routes.ts";

// Every page in the site's own languages has its language in the URL (/en/method, /de/method); the
// old unprefixed English addresses redirect to /en. Articles are listed from their files, drafts left
// out. Astro serves the redirects in development and writes them as pages; _redirects makes them
// permanent (301) where the site is served (dist/_redirects).
const blogSlugs = readdirSync("src/content/blog")
  .filter((file) => /^[^.]+\.md$/.test(file))
  .filter((file) => !/^draft:\s*true$/m.test(readFileSync(`src/content/blog/${file}`, "utf8")))
  .map((file) => file.replace(/\.md$/, ""));
const redirects = unprefixedRedirects(blogSlugs);

// Static site. build.format "file" writes /id/DE-DDG.html, which is served as /id/DE-DDG; the
// Turtle for the same resource sits next to it as /id/DE-DDG.ttl, and worker/ serves it instead of
// the page to clients that ask for Turtle (content negotiation).
// SITE_URL overrides the public origin (e.g. for a preview deployment).
//
// The sitemap lists every page, for search engines and Google Search Console; each page in the site's
// own languages lists its other language versions (/en, /de) as hreflang alternates. @astrojs/sitemap writes the parts
// (/sitemap-0.xml, -1 … at 50,000 URLs each) and an index, which we publish at the conventional
// /sitemap.xml (named in /robots.txt). Search Console itself is verified by a DNS
// record on the domain, not by anything here.
export default defineConfig({
  site: process.env.SITE_URL ?? "https://legalgraph.org",
  build: { format: "file" },
  trailingSlash: "never",
  redirects,
  integrations: [
    sitemap({
      i18n: { defaultLocale: "en", locales: { en: "en", de: "de" } },
      filter: (page) => !/\/404(\.html)?$/.test(page),
    }),
    {
      name: "sitemap-and-redirects",
      hooks: {
        "astro:build:done": async ({ dir }) => {
          await rename(new URL("sitemap-index.xml", dir), new URL("sitemap.xml", dir));
          const lines = Object.entries(redirects).map(([from, to]) => `${from} ${to} 301`);
          await writeFile(new URL("_redirects", dir), `${lines.join("\n")}\n`);
        },
      },
    },
  ],
  vite: { plugins: [tailwindcss()] },
});
