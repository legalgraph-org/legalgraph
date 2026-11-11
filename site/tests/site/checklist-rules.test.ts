import { describe, expect, it } from "vitest";

import checklist from "../../src/data/checklist.json";
import obligations from "../../src/data/obligations.json";
import { applicable, type Rule } from "../../src/lib/checklist-rules";

// The checklist page evaluates the rules in the browser; the scenarios (scenarios/*.yaml) fix what the
// Python rules layer gives each example business. Both must agree.
describe("checklist rules in the browser", () => {
  const rules = obligations as Rule[];
  it.each(checklist.scenarios.map((s) => [s.id, s] as const))("%s gets exactly its obligations", (_, scenario) => {
    const found = applicable(
      checklist.conditions,
      rules,
      new Set(scenario.facts),
      scenario.establishedIn ?? "",
      new Set(scenario.markets),
    );
    expect(found.map((r) => r.id).sort()).toEqual([...scenario.obligations].sort());
  });
});
