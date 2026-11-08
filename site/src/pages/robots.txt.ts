// robots.txt: everything may be crawled; the sitemap lists every page.
import type { APIRoute } from "astro";

export const GET: APIRoute = ({ site }) => {
  const origin = site ?? new URL("https://legalgraph.org");
  const body = ["User-agent: *", "Allow: /", "", `Sitemap: ${new URL("/sitemap.xml", origin).href}`, ""].join("\n");
  return new Response(body, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
