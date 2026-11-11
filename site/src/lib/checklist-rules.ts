// The rules layer as the checklist evaluates it in the browser, the same logic as
// src/legalgraph/rules.py (tests/site/checklist-rules.test.ts runs the scenarios through both). A rule
// applies when all its conditions hold and none of its exemptions does; derived conditions follow from
// others. A business offers its services where it is established as well as in its markets. A rule
// follows the markets when one of its conditions is tied to them (consumer contracts follow the
// consumer's country), else the establishment; national rules that refine a general one replace it
// when they cover every place it is followed in.

export interface Condition {
  id: string;
  anyOf: string[];
  allOf: string[];
  establishedIn: string | null;
  offersIn: string | null;
  within: string[];
}

export interface Rule {
  id: string;
  appliesWhen: string[];
  unless: string[];
  refines: string[];
  marketBased: boolean;
  within: string[];
}

/** Where the business is established: as given, or from a fact such as EstablishedInGermany (the narrowest). */
export function establishment(conditions: Condition[], facts: Set<string>, established: string): string {
  if (established) return established;
  const places = conditions.filter((c) => facts.has(c.id) && c.establishedIn);
  places.sort((a, b) => a.within.length - b.within.length);
  return places[0]?.establishedIn ?? "";
}

/** Where the business offers its services: its markets and the place it is established in. */
export function offeredIn(established: string, markets: Set<string>): Set<string> {
  return new Set([...markets, ...(established ? [established] : [])]);
}

/** The conditions that hold: the facts, those tied to where the business is established or offers its
 * services, and every derived condition they imply. */
export function holding(conditions: Condition[], facts: Set<string>, established: string, markets: Set<string>): Set<string> {
  established = establishment(conditions, facts, established);
  const offered = offeredIn(established, markets);
  const holds = new Set(facts);
  for (const c of conditions) {
    if (c.establishedIn && established && c.within.includes(established)) holds.add(c.id);
    if (c.offersIn && c.within.some((j) => offered.has(j))) holds.add(c.id);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const c of conditions) {
      if (holds.has(c.id)) continue;
      if ((c.anyOf.length && c.anyOf.some((x) => holds.has(x))) || (c.allOf.length && c.allOf.every((x) => holds.has(x)))) {
        holds.add(c.id);
        changed = true;
      }
    }
  }
  return holds;
}

/** Where the business follows a rule, within the rule's own jurisdiction. */
export function places(rule: Rule, established: string, markets: Set<string>): string[] {
  const where = rule.marketBased ? offeredIn(established, markets) : new Set(established ? [established] : []);
  return [...where].filter((p) => rule.within.includes(p)).sort();
}

/** The rules that apply; one refined by others that apply too is left out when they cover every place
 * it is followed in. */
export function applicable<R extends Rule>(
  conditions: Condition[],
  rules: R[],
  facts: Set<string>,
  established: string,
  markets: Set<string>,
): R[] {
  const holds = holding(conditions, facts, established, markets);
  established = establishment(conditions, facts, established);
  const found = rules.filter((r) => r.appliesWhen.every((c) => holds.has(c)) && !r.unless.some((c) => holds.has(c)));
  const replaced = (general: R) => {
    const refining = found.filter((r) => r.refines.includes(general.id));
    const covered = new Set(refining.flatMap((r) => r.within));
    return refining.length > 0 && places(general, established, markets).every((p) => covered.has(p));
  };
  return found.filter((r) => !replaced(r));
}
