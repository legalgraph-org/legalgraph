---
title: "Guest article: an Impressum template generator built on legalgraph"
description: legalgraph is a dataset, not an app. How Aimix built a browser tool on it that tells a website which imprint rules apply and writes the template, with every line traced back to the graph.
published: 2026-11-11
author: Aimix
category: Built on legalgraph
---

*A guest article by [Aimix](https://aimix.io), the company that started legalgraph and builds products for
small businesses on top of it.*

legalgraph is a dataset. It holds official law texts, the provisions marked in them, the rules those
provisions create and the conditions under which each rule applies, all as open data under
[CC BY 4.0](https://github.com/legalgraph-org/legalgraph/blob/main/LICENSE-DATA). What it deliberately is
not is an app for one particular job. The [checklist](/en/checklist) on this site shows what the data can
answer, but a business owner who needs an imprint for their website needs more than a list of rules: they
need the page itself.

That is where products come in. This article describes one of them, the
[Impressum template generator](https://aimix.io/en/impressum-template-generator) on aimix.io, and how it
uses the graph. Others can build the same kind of tool: everything it uses is in the
[downloads](/en/download).

## What the generator does

A visitor answers a few questions: where the business is established, whether the website is commercial,
who runs it, which registration numbers it has, whether it sells to consumers. As they answer, the rules
that apply appear one by one, each with the reason it applies and the provision behind it. At the end they
get the imprint as a template, in German and English for Germany and Austria, in Ukrainian and English for
Ukraine, with placeholders such as YOUR COMPANY NAME instead of their details. It asks for no personal
details, and the template is put together in the browser.

## How it uses the graph

**The rules come out of the graph, unchanged.** A handful of SPARQL queries select the imprint family: the
rules that are part of [provider identification](/en/rules) and the consumer dispute resolution statement,
in Germany, Austria, the EU and EEA, the UK and Ukraine. They return the rules with their conditions, the
provisions they cite with their quotes and English translations, and the information items each rule asks
for. The result is one JSON file the generator ships with. When the graph changes, the file is generated
again; nobody edits a rule by hand.

**It gives the same answers as the graph's own engine.** legalgraph has a rules engine that decides which
rules apply to a set of facts. The generator has a small copy of that logic in the browser. To make sure
the two never disagree, a dozen example businesses (a German GmbH, an Austrian news blog, a Ukrainian
online shop and so on) are run through legalgraph's engine when the file is generated, and the generator's
tests replay them against its own logic.

**Every line points back.** Each rule in the result links to its page on this site, such as
[the German Impressum rule](/id/DE-R-impressum) or [the EU-wide rule](/id/EU-R-service-provider-information),
where the quoted law text and its official source are one click away.

**It says what the graph doesn't know.** How well the generator covers a country is worked out from the
graph itself. Where a country has its own imprint rules in the graph, it says so. Where the graph has only
the EU-wide rules, with or without the country's implementing provision linked, the visitor is told that
national extras may be missing, and is offered the German rules as a strict baseline. Where the graph has
nothing, it says that too, instead of showing an empty list as if no rules existed.

## Dataset and products: who does what

The split is deliberate:

- **legalgraph** collects and checks the law: official texts, verified against their sources, with every
  rule traceable to the words it comes from. Its rules are marked as drafts until a lawyer has reviewed
  them, and they are a reading of the law, not legal advice.
- **Products** turn that into something a person can use for a task, with their own questions, wording
  and design, and their own responsibility for what they tell their users.

A product never needs to copy a rule or invent one. When a contributor corrects a rule here, every tool
built on the graph gets the correction with its next update.

## Build your own

The data is free to use under CC BY 4.0, with attribution such as *legalgraph by Aimix GmbH, licensed
under CC BY 4.0*. The [downloads](/en/download) page has the graph in Turtle, N-Triples and JSON-LD, and
the [method](/en/method) explains how each rule is made. If you build something on it, tell us on
[GitHub](https://github.com/legalgraph-org/legalgraph): we would like to list it here.
