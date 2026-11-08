/** Facets of a FilterList: groups of options; each entry carries the ids of the options it has. */
export interface FilterOption {
  id: string;
  label: string;
  count: number;
}

export interface FilterGroup {
  title: string;
  options: readonly FilterOption[];
}

/** The id of an option's radio. Option ids are made safe for ids and attribute selectors. */
export const filterInputId = (list: string, option: string) => `${list}-filter-${option}`;

export const tagId = (value: string) => value.toLowerCase().replace(/[^a-z0-9-]+/g, "-");

/**
 * The filter itself is CSS: when an option's radio is checked, entries without that tag hide
 * (radio + :has()), so it works without JavaScript.
 */
export function filterCss(list: string, groups: readonly FilterGroup[]): string {
  return groups
    .flatMap((group) => group.options)
    .map(
      (option) =>
        `[data-filter-list="${list}"]:has(#${filterInputId(list, option.id)}:checked) .filter-entry:not([data-tags~="${option.id}"]){display:none}`,
    )
    .join("\n");
}
