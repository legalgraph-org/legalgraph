/** The language switcher and dialog. */
export interface LanguageOption {
  /** BCP 47 code of the target page, used for hreflang and lang. */
  code: string;
  /** The language's own name, e.g. "Deutsch". */
  name: string;
  flag?: string;
  /** The same page in that language, or that language's home if the page has no translation. */
  href: string;
  current?: boolean;
}
