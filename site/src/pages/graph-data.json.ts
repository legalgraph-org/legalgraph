// The graph's nodes and edges as one static JSON file (/graph-data.json), fetched by the graph
// views when they first need it and cached by the browser, instead of being bundled into the
// JavaScript of every page that shows a graph. `laws` names every law, judgment and guideline, so
// the views can spell out abbreviations: its short name, its title in its own language, and in
// English.
import type { APIRoute } from "astro";
import data from "../data/graph.json";
import { loadGraph } from "../lib/data";

export const GET: APIRoute = async () => {
  const graph = await loadGraph();
  const laws = Object.fromEntries(
    [...graph.acts.values()].map((act) => {
      const own = act.data.titles.find((title) => title.lang !== "en") ?? act.data.titles[0];
      const english = act.data.titleEn ?? act.data.titles.find((title) => title.lang === "en")?.text ?? null;
      return [
        act.id,
        {
          short: act.data.shortName,
          title: own?.text ?? english ?? act.id,
          lang: own?.lang ?? "en",
          english: english && english !== own?.text ? english : null,
        },
      ];
    }),
  );
  return new Response(JSON.stringify({ ...data, laws }), { headers: { "Content-Type": "application/json" } });
};
