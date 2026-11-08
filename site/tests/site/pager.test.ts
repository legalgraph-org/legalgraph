import { describe, expect, it } from "vitest";

import { pageItems } from "../../src/scripts/filter-list";

// Shown as 1-based page numbers, "…" for a gap.
const labels = (page: number, pages: number) => pageItems(page, pages).map((item) => (item === "gap" ? "…" : item + 1));

describe("pageItems", () => {
  it("shows every page when there are few", () => {
    expect(labels(0, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(labels(3, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("keeps the first page, the last two and the current page with its neighbours", () => {
    expect(labels(0, 14)).toEqual([1, 2, 3, 4, "…", 13, 14]);
    expect(labels(6, 14)).toEqual([1, "…", 6, 7, 8, "…", 13, 14]);
    expect(labels(13, 14)).toEqual([1, "…", 10, 11, 12, 13, 14]);
  });

  it("shows a single missing page instead of an ellipsis", () => {
    expect(labels(3, 14)).toEqual([1, 2, 3, 4, 5, "…", 13, 14]);
    expect(labels(9, 14)).toEqual([1, "…", 9, 10, 11, 12, 13, 14]);
  });

  it("never shows more than nine buttons", () => {
    for (let pages = 1; pages <= 60; pages += 1) {
      for (let page = 0; page < pages; page += 1) expect(pageItems(page, pages).length).toBeLessThanOrEqual(9);
    }
  });
});
