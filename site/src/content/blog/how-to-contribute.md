---
title: How to contribute to legalgraph
description: The graph grows with every law, country and court decision someone adds. How a contribution works, from an issue to a reviewed pull request, and where it all leads.
published: 2026-11-07
category: The project
---

legalgraph will never be finished by one team. There are hundreds of laws that tell a website what to
show and do, in dozens of countries and languages, and courts and authorities read them anew every
month. The graph is built so that anyone who knows a piece of that law can add it, and anyone else can
check what they added.

This article walks through how that works. The [contributing guide](https://github.com/legalgraph-org/legalgraph/blob/main/CONTRIBUTING.md)
on GitHub has the commands.

## What you can add

The graph is designed to be extended in three directions.

### More laws

A country's privacy law, a rule on price display, a duty to name a dispute resolution body: each
is a law text from an official portal. You add the text as the portal publishes it, mark the paragraphs
that matter, and the graph is generated from your marks. Nobody types a quote in by hand, so nobody has
to take one on trust. The [method](/en/method) shows the whole path with one duty as the example.

### More countries

The graph covers the EU and most of Europe, the UK, Ukraine, the US and California, but in very
different depth. For some countries every provision comes from the official text; for others, entries
are still drafts from research notes. Bringing a country from drafts to its official texts is one of
the most useful contributions there is, and it needs someone who reads that country's law in its own
language.

### More court decisions

The law says what a website must do. Decisions show what happens when it doesn't: an injunction over a
cookie banner, a fine for cookies set without consent, damages for an embedded font. Each decision in the
graph records its outcome, who it was against, the provision it was for, and the point of the
judgment that says so, so a reader can check it against the decision's own words.

## How a contribution works

### 1. Start with an issue

Found a wrong citation, a law that has changed, or a translation that misses the point? [Open an
issue](https://github.com/legalgraph-org/legalgraph/issues) on GitHub with a link to the official text.
That alone is a contribution: someone can fix it, and everyone can see it is known.

If you plan to add something larger, such as a new country or a new kind of decision, open an issue first
too. It lets us agree on the scope before you put in the time.

### 2. Follow the ontology, or extend it

Everything in the graph uses one shared model, the ontology: what a legal act is, what a provision is,
what it means for a provision to *require* an information item, what a rule and its conditions are.
New data uses the terms that already exist. That is what makes a German provision and a French one
comparable, and a query run across every country at once possible.

Sometimes the term you need isn't there yet, because a law asks for something no other law in the graph
asks for. Then you add the term to the ontology in the same pull request, with an English definition
that states the law. A check rejects any term that isn't defined, so the data and the model cannot drift
apart. Changes to the model itself, such as new kinds of things or relations, are discussed in an issue
first, because they affect every country.

### 3. Open a pull request

The change goes to GitHub as a pull request. Before it does, one command runs everything a reviewer
would want checked: the law texts against their originals, the generated data against the annotated
texts, the graph against the ontology's rules, and the example businesses against the rules they must
get.

A maintainer then reads it the way a lawyer reads a brief: does the quote match the official text, does
the mark sit on the right paragraph, does the rule follow from the provisions it names. Where you have
interpreted the law rather than quoted it, the pull request says so, and the entry stays a draft until
someone qualified has reviewed it.

## From contributor to maintainer

Maintainers review and accept changes to the graph. Today that is the team that started it. We want it
to grow: contributors who make substantial, careful contributions over time can be invited to join the
maintainers and help decide what goes into the graph. Knowing a country's law, or the portals it is
published on, counts as much as writing code.

## Where this is going

The goal is a graph complete enough that a business owner can see which rules matter most for their
business: where it is established, where it sells, what its website does. Each rule comes with the
law it comes from, in the original words and in English.

That is not legal advice, and the graph never pretends to be. Rules are our reading of the law and are
marked as drafts until a lawyer reviews them. Their purpose is awareness. Too many businesses learn
about a duty from a warning letter. The law is public, and information about what it asks should be
open and accessible too, not locked in paywalled guides or paraphrased beyond recognition.

## Built for AI agents, too

More and more people ask an AI assistant first. An assistant that answers from memory paraphrases, and
may be out of date or simply wrong. One that can read the graph can look up which rules apply to a
business, quote the provision behind each, and link to it, so its answer comes with sources a person can
check.

That makes the graph a starting point for agents doing initial research: a first map of the rules that
matter, which a business owner, or their lawyer, can then follow to the law itself. Every contribution
makes that map more complete, for people and agents alike.

## Start here

- The repository: [github.com/legalgraph-org/legalgraph](https://github.com/legalgraph-org/legalgraph).
  Leave a star, clone it, and run `make check`.
- [CONTRIBUTING.md](https://github.com/legalgraph-org/legalgraph/blob/main/CONTRIBUTING.md): the
  practical guide, from setting up to adding a law.
- [Issues](https://github.com/legalgraph-org/legalgraph/issues): report what is wrong, or propose what is
  missing.
- The [method](/en/method) and the [glossary](/en/glossary), if RDF, Turtle and SPARQL are new to you.
