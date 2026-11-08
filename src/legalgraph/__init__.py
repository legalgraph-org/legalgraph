"""Utilities for legalgraph: load, validate, query and export."""

from rdflib import Namespace

LGO = Namespace("https://legalgraph.org/ontology#")
LGV = Namespace("https://legalgraph.org/vocab/")
LG = Namespace("https://legalgraph.org/id/")
ELI = Namespace("http://data.europa.eu/eli/ontology#")

PREFIXES = {"lgo": LGO, "lgv": LGV, "lg": LG, "eli": ELI}
