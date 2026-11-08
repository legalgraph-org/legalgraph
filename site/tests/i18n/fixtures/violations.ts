import type { Translate } from "../../../src/i18n/t";

export function violations(t: Translate, name: string): string[] {
  const tr = t;
  const { t: renamed } = { t };
  const holder = { translate: t };
  return [
    t(name),
    t(`Hello ${name}`),
    t("Hello " + name),
    tr("Aliased"),
    renamed("Renamed"),
    holder.translate("Held"),
    t("x".repeat(301)),
  ];
}
