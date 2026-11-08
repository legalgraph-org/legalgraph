import type { Translate } from "../i18n/t";
import type { FilterLabels } from "../scripts/filter-list";

/** The words a FilterList writes (its pager, counts and legend), in the page's language. */
export const filterLabels = (t: Translate): FilterLabels & { filter: string; pages: string } => ({
  filter: t("Filter"),
  pages: t("Pages"),
  previous: t("‹ Previous"),
  next: t("Next ›"),
  all: t("All"),
  show: t("Show"),
  perPage: t("per page"),
  entriesPerPage: t("Entries per page"),
  // The script fills these in; {braces} are kept for it, so they are passed through as values.
  matching: t("{shown} of {total} match", { shown: "{shown}", total: "{total}" }),
  range: t("{from}–{to} of {total}", { from: "{from}", to: "{to}", total: "{total}" }),
  allCount: t("All {total}", { total: "{total}" }),
});
