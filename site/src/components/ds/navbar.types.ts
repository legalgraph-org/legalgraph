/**
 * Navbar data. The navbar
 * renders the items twice: as the desktop bar (menus open on hover and keyboard focus, no
 * JavaScript) and inside the mobile `<details>` menu.
 */
export interface NavLink {
  label: string;
  href: string;
  /** The page being shown: rendered with aria-current="page". */
  current?: boolean;
}

/** One entry of a menu panel. Without `href` it is shown disabled (e.g. "Coming soon"). */
export interface NavMenuEntry {
  label: string;
  href?: string;
  description?: string;
  /** A short glyph shown in a tile. */
  icon?: string;
  /** A pill next to the label, e.g. "Coming soon". */
  badge?: string;
  current?: boolean;
}

export interface NavMenuGroup {
  title?: string;
  entries: readonly NavMenuEntry[];
}

export interface NavMenu {
  label: string;
  /** Makes the menu's own label a link too. */
  href?: string;
  groups: readonly NavMenuGroup[];
  width?: "md" | "lg";
  current?: boolean;
}

export type NavItem = ({ kind: "link" } & NavLink) | ({ kind: "menu" } & NavMenu);

export function panelWidthClass(width: NavMenu["width"]): string {
  return width === "lg" ? "w-[min(40rem,calc(100vw-2rem))]" : "w-[min(26rem,calc(100vw-2rem))]";
}
