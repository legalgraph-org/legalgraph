import { LOCALE_TAGS, type SupportedLocale } from "./locales";

/**
 * A content date (front matter "YYYY-MM-DD", which Date reads as UTC midnight), in UTC: in the build's
 * own time zone it would show the day before wherever that zone is behind UTC.
 */
export function formatDate(locale: SupportedLocale, date: Date): string {
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(date);
}
