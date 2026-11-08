import type { Translate } from "../../../src/i18n/t";

export const long = (t: Translate) =>
  t(
    "This message is deliberately long. It goes well beyond two sentences, so the extractor must warn that it belongs in a content collection rather than in the gettext catalogs. Translators handle long copy better as markdown, where paragraphs and links are natural. It is still extracted, and the build keeps working, but the warning stays visible in every extraction run until the copy moves.",
  );
