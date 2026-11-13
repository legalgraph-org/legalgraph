"""Where sources live, the annotation vocabulary of the annotated XML, and what an index may say."""

import re

from legalgraph import LG, LGO, LGV
from legalgraph.load import REPO_ROOT

ANNOTATION_NS = "https://legalgraph.org/ns/annotation#"
LAW_NS = "https://legalgraph.org/ns/law#"
CLML_NS = "http://www.legislation.gov.uk/namespaces/legislation"
AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
SOURCES_DIR = REPO_ROOT / "sources"
EXTRACTED_DIR = REPO_ROOT / "data" / "extracted"
LAW_SCHEMA = REPO_ROOT / "schemas" / "law.xsd"
USER_AGENT = "legalgraph (+https://legalgraph.org)"

ROOT_ATTRIBUTES = {"act", "jurisdiction", "act-type", "transposes", "url"}
# Annotation → (namespace of its values, predicate). The first group are the roles a provision needs
# at least one of; the second relate it to provisions elsewhere.
ROLE_PREDICATES = {
    "regulates": (LGV, LGO.regulates),
    "enforces": (LGV, LGO.enforces),
    "defines": (LGV, LGO.defines),
    "authorises": (LG, LGO.authorises),
    "explains": (LGV, LGO.explains),
    "interprets": (LG, LGO.interprets),
    "specifies": (LG, LGO.specifies),
    "applies": (LG, LGO.applies),
    "penalises": (LG, LGO.penalises),
}
LINK_PREDICATES = {
    "implements": (LG, LGO.implements),
    "takes-precedence-over": (LG, LGO.takesPrecedenceOver),
    "refers-to": (LG, LGO.refersTo),
    "proposes-to-amend": (LG, LGO.proposesToAmend),
}
PROVISION_ROLES = tuple(ROLE_PREDICATES)
PROVISION_ATTRIBUTES = {"provision", "citation", "url", "requires", *ROLE_PREDICATES, *LINK_PREDICATES}
# An authored parallel (a translation written in schemas/law.xsd) annotates only where a provision is
# and where it is published: lga:provision and lga:url; the root carries the usual act attributes.
PARALLEL_PROVISION_ATTRIBUTES = {"provision", "url"}
# The kind of document the root's lga:act-type makes it: legislation, a court decision or guidance.
DOCUMENT_CLASSES = {
    "Judgment": LGO.CourtDecision,
    "Guidelines": LGO.Guidance,
    "AuthorityDecision": LGO.AuthorityDecision,
}
ITEM_ATTRIBUTES = {"requires", "defines"}
# On what terms an original may be kept and republished (source.yaml `licence`, vocab/licences.ttl).
# Someone else's writing that none of these covers is not kept: it goes into sources/link-only.yaml.
LICENCES = {
    "public-domain": LGV.PublicDomain,
    "official-work": LGV.OfficialWork,
    "licence-ouverte-2.0": LGV.LicenceOuverte2,
    "ogl-3.0": LGV.OpenGovernmentLicence3,
    "reuse-with-attribution": LGV.ReuseWithAttribution,
}
LINK_ONLY = SOURCES_DIR / "link-only.yaml"
LINK_ONLY_OUTPUT = EXTRACTED_DIR / "link-only.ttl"
EXCERPT_LIMIT = 300  # characters: one or two sentences of someone else's work, never more

# Removing these from an annotated official XML must give back the original bytes.
STRIP_PATTERNS = [
    re.compile(rb' xmlns:lga="' + re.escape(ANNOTATION_NS.encode()) + rb'"'),
    re.compile(rb' lga:[A-Za-z][A-Za-z-]*="[^"]*"'),
]
