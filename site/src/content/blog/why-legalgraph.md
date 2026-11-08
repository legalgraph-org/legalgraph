---
title: Why we built legalgraph
description: Articles about website law make claims. We wanted every claim to link to the words of the law it comes from.
published: 2026-11-07
category: The project
---

Aimix builds websites for small businesses. Every one of those websites has to follow the law: it must
name who runs it, ask before it sets cookies that are not needed, let a subscriber cancel as easily as they
signed up. When we started writing about those duties for our customers, we kept running into the same
problem. It was easy to say what a website must do. It was hard to show where that comes from, in a way a
reader could check.

legalgraph is how we solved that for ourselves, and we publish it so that others don't have to solve it
again.

## The claim nobody can check

Read a few guides on website compliance and you will find sentences like these:

- *Your imprint needs your VAT number.*
- *Analytics needs consent.*
- *A subscription needs a cancel button.*

Each is roughly right. None of them tells you which law says so, what exactly it says, whether it applies to
you, or whether it still says that today. The source is paraphrased, or out of date, or not given at all.
A reader who wants to be sure has two options: trust the author, or find the law and read it themselves.

Finding the law is harder than it sounds. It sits on a different official portal in every country, often
only in that country's language, and a duty is usually split across several provisions: one sets the
duty, another defines who it covers, a third sets the fine.

## What a claim should come with

We decided that every statement we make about website law has to arrive with its evidence attached.

### The words of the law

Not a summary of the law, but the paragraph itself, quoted word for word from the text the official portal
publishes. The original file is kept unchanged with its hash and the date it was downloaded, so anyone can
fetch it again and compare. The [method](/en/method) describes how each quote is checked against that file
mechanically, so a quote cannot silently drift from what was published.

### A translation that says what it is

Most of Europe's website law is not in English. Where an official English version exists, we use it and say
so. Where it doesn't, the English is a machine translation, labelled as one, and it stays a draft until a
person reviews it. Nothing we wrote is passed off as official text.

### Who checked it, and how far

Every provision carries a review status. *Source checked* means its wording has been compared with the
official text. *Draft* means it has not been yet. The same goes for our readings of the law: a rule starts
as a draft and stays one until a lawyer reviews it.

## One claim, followed to its source

Take the first claim above, narrowed down: *a German business website must show its VAT identification
number, if it has one.* In legalgraph that is a rule, [Impressum: VAT identification
number](/id/DE-R-impressum-vat), and it states when it applies: the business is established in Germany, runs
a business website, and has a VAT ID.

The rule links to the provision it comes from, [§ 5 Abs. 1 DDG](/id/DE-DDG-s5-1), the German Digital
Services Act. There you find point 6 of that paragraph in the original German, with its English translation
next to it. The provision links to [the file from gesetze-im-internet.de](/id/DE-DDG-source) that the quote
was checked against.

The trail does not stop at the border. The German duty implements [Article 5 of the e-Commerce
Directive](/id/EU-R-service-provider-information), so a business in Austria or France has the same duty,
under its own country's law, and the graph names that law too.

Three clicks, from a claim to the words that justify it. That is the whole idea.

## Why open data, and a project of its own

We could have kept this as an internal tool. We publish it instead, as open data under CC BY 4.0, for two
reasons.

First, a claim only becomes checkable when the evidence is public. Anyone writing about website law,
building a compliance tool or teaching it can link to an entry instead of paraphrasing it, and their readers
can follow the link.

Second, links only work if they last. Every entry in the graph has a permanent address, such as
`legalgraph.org/id/DE-DDG-s5-1`. Once other people's articles, data and tools point to an address, it must
never change. Keeping the graph on its own domain, apart from any company's brand, keeps those addresses
stable and lets lawyers, researchers and public bodies contribute to a neutral project. Aimix's own articles
and products use the graph like anyone else.

## What it is not

legalgraph is structured research by researchers, not lawyers. It is not legal advice, and it does not
replace one. What it does is make the starting point visible: which provision, which words, which version,
and how sure we are about each of them.

## Try it

- The [checklist](/en/checklist) turns a few facts about a business into the rules that apply to it, each with
  its sources.
- [Countries](/en/countries) shows how much of each jurisdiction's website law is in the graph so far.
- [Law texts](/en/sources) lists every original with its hash, and the data can be downloaded in full.

If you find a wrong reading, an outdated text, or a law we should add, [open an issue on GitHub](https://github.com/legalgraph-org/legalgraph/issues)
or [write to us](mailto:contact@aimix.io). Every statement in the graph is an annotation on the law's own words,
so a correction is a small change anyone can review. [How to contribute](/en/blog/how-to-contribute) explains the rest.
