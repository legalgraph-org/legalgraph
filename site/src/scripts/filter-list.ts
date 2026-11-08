/**
 * The script of a FilterList (components/ds/FilterList.astro). Without it, the filters on the left
 * work in CSS and every entry shows. With it:
 * - the search box appears and keeps the entries whose data-search has every typed word;
 * - the checked filter is applied here too, so the list knows what it shows and can count it;
 * - with data-page-size, the matching entries show a page at a time, with Previous / numbers / Next
 *   and a choice of how many per page (10, 25, 50, 100 or all; the
 *   page size given is the default). Choosing a filter or typing goes back to page 1.
 * A link to an entry (#id) opens the page that holds it.
 * The filter, the search, the page and the page size are kept in the URL (?filter=, ?q=, ?page=,
 * ?per=), so a view can be shared or linked to (/en/rules?filter=j-de); the page size is also remembered
 * on this browser.
 */
/**
 * The page buttons to show, 0-based, with "gap" for an ellipsis: always the first page and the last
 * two (so the reader sees how many there are), the current page with one on each side, and a few
 * more near either end. A gap of a single page shows that page instead of "…".
 */
export function pageItems(page: number, pages: number): (number | "gap")[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, index) => index);
  const shown = new Set([0, pages - 2, pages - 1, page - 1, page, page + 1]);
  if (page <= 2) [1, 2, 3].forEach((index) => shown.add(index));
  if (page >= pages - 3) [pages - 5, pages - 4, pages - 3].forEach((index) => shown.add(index));
  const sorted = [...shown].filter((index) => index >= 0 && index < pages).sort((a, b) => a - b);
  const items: (number | "gap")[] = [];
  sorted.forEach((index, position) => {
    const previous = sorted[position - 1];
    if (previous !== undefined && index - previous === 2) items.push(index - 1);
    else if (previous !== undefined && index - previous > 2) items.push("gap");
    items.push(index);
  });
  return items;
}

/** The words the script writes, from the list's data-labels (FilterList.astro), in the page's language. */
export interface FilterLabels {
  previous: string;
  next: string;
  all: string;
  show: string;
  perPage: string;
  entriesPerPage: string;
  /** {shown} of {total} match */
  matching: string;
  /** {from}–{to} of {total} */
  range: string;
  /** All {total} */
  allCount: string;
}

export const ENGLISH_LABELS: FilterLabels = {
  previous: "‹ Previous",
  next: "Next ›",
  all: "All",
  show: "Show",
  perPage: "per page",
  entriesPerPage: "Entries per page",
  matching: "{shown} of {total} match",
  range: "{from}–{to} of {total}",
  allCount: "All {total}",
};

const fill = (template: string, values: Record<string, number>) =>
  template.replace(/\{(\w+)\}/g, (match, name: string) => (name in values ? String(values[name]) : match));

export function startFilterLists(): void {
  for (const root of document.querySelectorAll<HTMLElement>("[data-filter-list]")) {
    const labels: FilterLabels = { ...ENGLISH_LABELS, ...JSON.parse(root.dataset.labels ?? "{}") };
    const entries = [...root.querySelectorAll<HTMLElement>(".filter-entry")];
    const radios = [...root.querySelectorAll<HTMLInputElement>("input[data-option]")];
    const search = root.querySelector<HTMLInputElement>("[data-filter-search]");
    const box = root.querySelector<HTMLElement>("[data-filter-search-box]");
    const empty = root.querySelector<HTMLElement>("[data-filter-empty]");
    const status = root.querySelector<HTMLElement>("[data-filter-status]");
    const pager = root.querySelector<HTMLElement>("[data-filter-pager]");
    const list = root.querySelector<HTMLElement>("[data-filter-entries]");
    const paged = Boolean(Number(root.dataset.pageSize));
    const defaultSize = Number(root.dataset.pageSize) || 0;
    const SIZES = [10, 25, 50, 100, 0]; // 0: all
    const stored = `filter-list-per-page:${root.dataset.filterList}`;
    if (!search || !box) continue;
    box.hidden = false;

    const url = new URL(location.href);
    const filter = url.searchParams.get("filter");
    const preset = filter ? radios.find((radio) => radio.dataset.option === filter) : undefined;
    if (preset) preset.checked = true;
    search.value = url.searchParams.get("q") ?? "";
    let page = Math.max(0, Number(url.searchParams.get("page") ?? 1) - 1);
    const asked = url.searchParams.get("per") ?? localStorage.getItem(stored);
    // Lists without a pager (no data-page-size) always show everything.
    let pageSize = !paged ? 0 : asked === "all" ? 0 : asked !== null && SIZES.includes(Number(asked)) ? Number(asked) : defaultSize;

    const matching = () => {
      const option = radios.find((radio) => radio.checked)?.dataset.option ?? "";
      const words = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
      return entries.filter(
        (entry) =>
          (!option || (entry.dataset.tags ?? "").split(" ").includes(option)) &&
          words.every((word) => (entry.dataset.search ?? "").includes(word)),
      );
    };

    const button = (label: string, target: number, options: { current?: boolean; disabled?: boolean } = {}) => {
      const element = document.createElement("button");
      element.type = "button";
      element.textContent = label;
      element.className = "control min-w-9 py-1 disabled:opacity-40";
      element.disabled = Boolean(options.disabled);
      if (options.current) {
        element.setAttribute("aria-current", "page");
        element.classList.add("is-active");
      }
      element.addEventListener("click", () => {
        page = target;
        render();
        list?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return element;
    };

    const render = () => {
      const shown = matching();
      const pages = pageSize ? Math.max(1, Math.ceil(shown.length / pageSize)) : 1;
      page = Math.min(page, pages - 1);
      const from = pageSize ? page * pageSize : 0;
      const visible = new Set(pageSize ? shown.slice(from, from + pageSize) : shown);
      for (const entry of entries) entry.hidden = !visible.has(entry);
      if (empty) empty.hidden = shown.length > 0;
      const words = search.value.trim();
      if (status) status.textContent = words || shown.length !== entries.length ? fill(labels.matching, { shown: shown.length, total: entries.length }) : "";

      if (pager && paged) {
        pager.hidden = shown.length === 0;
        const numbers = document.createElement("div");
        numbers.className = "flex flex-wrap gap-1.5";
        numbers.append(button(labels.previous, page - 1, { disabled: page === 0 }));
        for (const item of pageItems(page, pages)) {
          if (item === "gap") {
            const gap = document.createElement("span");
            gap.className = "px-1 self-center text-muted-foreground";
            gap.setAttribute("aria-hidden", "true");
            gap.textContent = "…";
            numbers.append(gap);
          } else {
            numbers.append(button(String(item + 1), item, { current: item === page }));
          }
        }
        numbers.append(button(labels.next, page + 1, { disabled: page >= pages - 1 }));
        numbers.hidden = pages <= 1;
        const where = document.createElement("div");
        where.className = "flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground";
        const count = document.createElement("p");
        count.textContent = pageSize
          ? fill(labels.range, { from: from + 1, to: Math.min(from + pageSize, shown.length), total: shown.length })
          : fill(labels.allCount, { total: shown.length });
        const choose = document.createElement("label");
        choose.className = "inline-flex items-center gap-1.5";
        const select = document.createElement("select");
        select.className = "control py-1";
        select.setAttribute("aria-label", labels.entriesPerPage);
        for (const size of SIZES) {
          const option = document.createElement("option");
          option.value = size ? String(size) : "all";
          option.textContent = size ? String(size) : labels.all;
          option.selected = size === pageSize;
          select.append(option);
        }
        select.addEventListener("change", () => {
          pageSize = select.value === "all" ? 0 : Number(select.value);
          localStorage.setItem(stored, select.value);
          page = 0;
          render();
        });
        choose.append(labels.show, select, labels.perPage);
        where.append(count, choose);
        pager.replaceChildren(where, numbers);
      }

      const next = new URL(location.href);
      const option = radios.find((radio) => radio.checked)?.dataset.option;
      if (option) next.searchParams.set("filter", option);
      else next.searchParams.delete("filter");
      if (words) next.searchParams.set("q", words);
      else next.searchParams.delete("q");
      if (pageSize && page > 0) next.searchParams.set("page", String(page + 1));
      else next.searchParams.delete("page");
      if (paged && pageSize !== defaultSize) next.searchParams.set("per", pageSize ? String(pageSize) : "all");
      else next.searchParams.delete("per");
      history.replaceState(null, "", next);
    };

    search.addEventListener("input", () => {
      page = 0;
      render();
    });
    root.addEventListener("change", (event) => {
      if ((event.target as HTMLElement).matches("input[data-option]")) {
        page = 0;
        render();
      }
    });
    render();

    // A link to one entry (#id, as the glossary's tooltips give) opens the page that holds it,
    // clearing a filter or search that hides it, and scrolls to it.
    const reveal = () => {
      const target = entries.find((entry) => entry.id && entry.id === decodeURIComponent(location.hash.slice(1)));
      if (!target) return;
      if (!matching().includes(target)) {
        search.value = "";
        const all = radios.find((radio) => !radio.dataset.option);
        if (all) all.checked = true;
      }
      if (pageSize) page = Math.floor(matching().indexOf(target) / pageSize);
      render();
      target.scrollIntoView({ block: "start" });
    };
    reveal();
    addEventListener("hashchange", reveal);
  }
}
