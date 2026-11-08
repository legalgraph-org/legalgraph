// Cases: what a decision ordered, in words a reader can scan.
import type { Act } from "./data";

export const KIND_LABELS: Record<Act["data"]["kind"], string> = {
  act: "Legal act",
  decision: "Court decision",
  enforcement: "Authority decision",
  guidance: "Guidance",
};

export const KIND_PLURALS: Record<Act["data"]["kind"], string> = {
  act: "Legal acts",
  decision: "Court decisions",
  enforcement: "Authority decisions",
  guidance: "Guidelines",
};

export type Outcome = Act["data"]["outcomes"][number];

const money = (amount: number, currency: string) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);

/** "Fine of €150,000,000", "Injunction". */
export function outcomeSummary(outcome: Outcome): string {
  return outcome.amount !== null && outcome.currency
    ? `${outcome.type} of ${money(outcome.amount, outcome.currency)}`
    : outcome.type;
}
