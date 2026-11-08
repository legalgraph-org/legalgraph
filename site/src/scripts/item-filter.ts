// Client-side filter for /items: disclosure-type pills (several can be on at once — a row shows
// when its group is selected, i.e. OR) plus a free-text search that narrows the result further
// (AND). A disclosure group header stays visible as long as one of its rows does.
export function startItemFilter(root: HTMLElement): void {
  const pills = [...root.querySelectorAll<HTMLButtonElement>("[data-items-filter-type]")];
  const search = root.querySelector<HTMLInputElement>("[data-items-filter-search]");
  const clear = root.querySelector<HTMLButtonElement>("[data-items-filter-clear]");
  const empty = document.querySelector<HTMLElement>("[data-items-filter-empty]");
  const table = document.querySelector<HTMLElement>("[data-items-table]");
  if (!search || !table) return;
  root.hidden = false;

  const rows = [...table.querySelectorAll<HTMLElement>("tr[data-filter]")];
  const headers = new Map<string, HTMLElement>();
  for (const header of table.querySelectorAll<HTMLElement>("tr[data-group-header]")) {
    headers.set(header.dataset.groupHeader!, header);
  }
  const selected = new Set<string>();

  const apply = (): void => {
    const query = search.value.trim().toLowerCase();
    for (const row of rows) {
      row.hidden =
        (selected.size > 0 && !selected.has(row.dataset.group!)) ||
        (query !== "" && !(row.dataset.filter ?? "").includes(query));
    }
    for (const [id, header] of headers) {
      header.hidden = !rows.some((row) => row.dataset.group === id && !row.hidden);
    }
    if (empty) empty.hidden = rows.some((row) => !row.hidden);
  };

  for (const pill of pills) {
    pill.addEventListener("click", () => {
      const id = pill.dataset.itemsFilterType!;
      const on = !selected.has(id);
      selected[on ? "add" : "delete"](id);
      pill.setAttribute("aria-pressed", String(on));
      apply();
    });
  }
  search.addEventListener("input", () => {
    if (clear) clear.hidden = search.value === "";
    apply();
  });
  clear?.addEventListener("click", () => {
    search.value = "";
    clear.hidden = true;
    search.focus();
    apply();
  });
}
