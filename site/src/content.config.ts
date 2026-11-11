// Collections written by `legalgraph generate-site` (src/legalgraph/site.py) into src/data/.
// The schemas are the contract between the Python side and the pages: a mismatch fails the build.
// Articles and legal pages are written by hand, in Markdown under src/content/.
import { defineCollection } from "astro:content";
import { file, glob } from "astro/loaders";
import { z } from "astro/zod";

const text = z.object({ text: z.string(), lang: z.string() });
const ids = z.array(z.string());

const jurisdictions = defineCollection({
  loader: file("src/data/jurisdictions.json"),
  schema: z.object({
    code: z.string(),
    kind: z.enum(["country", "organisation", "subdivision"]),
    label: z.string(),
    memberOf: ids,
    members: ids,
    languages: z.array(z.string()),
    noticeNames: z.array(text),
    comment: z.string().nullable(),
    acts: ids,
  }),
});

// What a decision ordered for one party (a fine, damages, an injunction), with the point of the
// decision that states it.
const outcome = z.object({
  id: z.string(),
  type: z.string(),
  against: z.array(z.string()),
  amount: z.number().nullable(),
  currency: z.string().nullable(),
  statedIn: ids,
  forBreachOf: ids,
  sanctionedUnder: ids,
  comment: z.string().nullable(),
  reviewStatus: z.string(),
});

// Someone else's page that backs up a decision: linked, with at most one short excerpt.
const reference = z.object({
  id: z.string(),
  title: z.string().nullable(),
  publisher: z.string().nullable(),
  url: z.string().nullable(),
  date: z.string().nullable(),
  excerpt: z.string().nullable(),
  excerptLang: z.string().nullable(),
  locator: z.string().nullable(),
  claim: z.string().nullable(),
});

const acts = defineCollection({
  loader: file("src/data/acts.json"),
  schema: z.object({
    kind: z.enum(["act", "decision", "enforcement", "guidance"]),
    ecli: z.string().nullable(),
    titles: z.array(text),
    titleEn: z.string().nullable(),
    shortName: z.string().nullable(),
    actType: z.string(),
    jurisdiction: z.string(),
    sourceUrl: z.string().nullable(),
    localId: z.string().nullable(),
    dateDocument: z.string().nullable(),
    lastAmended: z.string().nullable(),
    firstInForce: z.string().nullable(),
    noLongerInForce: z.string().nullable(),
    transposes: ids,
    transposedBy: ids,
    repeals: ids,
    repealedBy: ids,
    authorisedBy: ids,
    reviewStatus: z.string(),
    comments: z.array(text),
    documents: ids,
    provisions: ids,
    caseNumber: z.string().nullable(),
    creator: z.string().nullable(),
    outcomes: z.array(outcome),
    illustrates: ids,
    follows: ids,
    followedBy: ids,
    references: z.array(reference),
  }),
});

const translation = z.object({
  text: z.string().nullable(),
  method: z.string(),
  by: z.array(z.string()),
  on: z.string().nullable(),
  status: z.string(),
  reviewedBy: z.array(z.string()),
});

const quote = z.object({
  id: z.string(),
  lang: z.string(),
  text: z.string(),
  sourceUrl: z.string().nullable(),
  retrievedOn: z.string().nullable(),
  official: z.boolean(),
  translation: translation.nullable(),
  // The same provision in the other official languages (EU acts): equally authentic, not translations.
  versions: z.array(
    z.object({ id: z.string(), lang: z.string(), text: z.string(), sourceUrl: z.string().nullable(), official: z.boolean() }),
  ),
});

const provisions = defineCollection({
  loader: file("src/data/provisions.json"),
  schema: z.object({
    citation: z.string(),
    act: z.string(),
    jurisdiction: z.string(),
    sourceUrl: z.string().nullable(),
    reviewStatus: z.string(),
    regulates: ids,
    enforces: ids,
    defines: ids,
    authorises: ids,
    requires: ids,
    implements: ids,
    implementedBy: ids,
    explains: ids,
    interprets: ids,
    interpretedBy: ids,
    specifies: ids,
    specifiedBy: ids,
    takesPrecedenceOver: ids,
    givesWayTo: ids,
    refersTo: ids,
    referredToBy: ids,
    proposesToAmend: ids,
    proposedAmendments: ids,
    applies: ids,
    appliedBy: ids,
    penalises: ids,
    penalisedBy: ids,
    continues: ids,
    continuedBy: ids,
    readUnder: ids,
    readUnderBy: ids,
    comments: z.array(text),
    document: z.string().nullable(),
    sourceElement: z.string().nullable(),
    quotes: z.array(quote),
  }),
});

const concepts = defineCollection({
  loader: file("src/data/concepts.json"),
  schema: z.object({
    kind: z.enum(["item", "disclosure", "concept", "condition", "action", "role", "term"]),
    scheme: z.string().nullable(),
    label: z.string(),
    labels: z.array(text),
    altLabels: z.array(text),
    definition: z.string().nullable(),
    broader: ids,
    narrower: ids,
    requiredBy: ids,
    definedBy: ids,
    regulatedBy: ids,
    enforcedBy: ids,
    explainedBy: ids,
    question: z.string().nullable(),
    basedOn: ids,
    holdsWhenAny: ids,
    holdsWhenAll: ids,
    usedBy: ids,
  }),
});

// The reading view of a source document: its annotated sections (a § each), line by line.
const section = z.object({
  num: z.string(),
  title: z.string().nullable(),
  titles: z.record(z.string(), z.string()),
  source: z.string(),
  xpath: z.string(),
  xml: z.string(),
  paragraphs: z.array(
    z.object({
      xpath: z.string(),
      provision: z.string().nullable(),
      annotations: z.record(z.string(), z.string()),
      lines: z.array(z.object({ text: z.string(), requires: z.array(z.string()), defines: z.array(z.string()) })),
      versions: z.record(z.string(), z.array(z.string())),
    }),
  ),
});

const documents = defineCollection({
  loader: file("src/data/documents.json"),
  schema: z.object({
    act: z.string(),
    path: z.string(),
    annotatedFile: z.string().nullable(),
    sha256: z.string(),
    sourceUrl: z.string(),
    retrievedOn: z.string(),
    mediaType: z.string().nullable(),
    portalBuildDate: z.string().nullable(),
    legalStatus: z.array(z.object({ text: z.string(), lang: z.string(), english: z.string().nullable() })),
    licence: z.string().nullable(),
    licenceBasis: z.string().nullable(),
    language: z.string().nullable(),
    versionOf: z.string().nullable(),
    versions: ids,
    sections: z.array(section),
    related: z.array(
      z.object({
        role: z.enum(["authentic", "amendment", "corrigendum"]),
        mediaType: z.string(),
        title: z.string(),
        path: z.string(),
        language: z.string(),
        url: z.string(),
        sha256: z.string(),
        retrievedOn: z.string(),
        corrects: z.array(z.string()),
      }),
    ),
  }),
});

// The rules layer (data/rules/): obligations with the conditions they apply under.
const obligations = defineCollection({
  loader: file("src/data/obligations.json"),
  schema: z.object({
    label: z.string(),
    comment: z.string().nullable(),
    appliesIn: z.string(),
    appliesWhen: ids,
    unless: ids,
    items: ids,
    actions: ids,
    disclosure: z.string().nullable(),
    establishedBy: ids,
    refines: ids,
    // National provisions implementing those it is established by, by jurisdiction.
    implementedBy: z.record(z.string(), ids),
    // Whether it follows the business's markets rather than its establishment, and the
    // jurisdictions it applies in (rules.places in the CLI).
    marketBased: z.boolean(),
    within: ids,
    bearer: ids,
    deonticType: z.string(),
    reviewStatus: z.string(),
    // Decisions that show the rule at work, newest first, and the provisions that fine a breach.
    cases: ids,
    penalties: ids,
  }),
});

// Markdown is translated per file: <name>.md is English, <name>.<locale>.md its
// translation. The id keeps the file name, so "why-legalgraph.de" stays distinguishable.
const fileId = ({ entry }: { entry: string }) => entry.replace(/\.md$/, "");

// Articles (/blog). Drafts are left out of the build.
const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "src/content/blog", generateId: fileId }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    published: z.coerce.date(),
    updated: z.coerce.date().optional(),
    author: z.string().default("legalgraph"),
    /** Groups articles on the index, in the article's own language, e.g. "The project". */
    category: z.string().optional(),
    /** Shown large at the top of the index; without one, the newest article is. */
    featured: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// Legal pages (/legal/<id>): imprint, privacy, terms of use.
const legal = defineCollection({
  loader: glob({ pattern: "*.md", base: "src/content/legal", generateId: fileId }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    updated: z.coerce.date().optional(),
    /** Not yet written: the page says so instead of pretending to be complete. */
    pending: z.boolean().default(false),
  }),
});

// The glossary (/glossary): the abbreviations the site's own pages use, one entry per term with its
// text in each language (src/content/glossary.yaml, where the fields are explained).
const glossaryText = z.object({
  match: z.array(z.string()),
  expansion: z.string(),
  short: z.string().max(200),
  body: z.string(),
});
const glossary = defineCollection({
  loader: file("src/content/glossary.yaml"),
  schema: z.object({
    kind: z.enum(["law", "body", "business", "standard", "licence", "service"]),
    graph: z.string().optional(),
    source: z.object({ label: z.string(), url: z.url() }).optional(),
    original: text.optional(),
    seeAlso: ids.default([]),
    en: glossaryText,
    de: glossaryText,
  }),
});

export const collections = { jurisdictions, acts, provisions, concepts, documents, obligations, blog, legal, glossary };

export type Quote = z.infer<typeof quote>;
export type Section = z.infer<typeof section>;
