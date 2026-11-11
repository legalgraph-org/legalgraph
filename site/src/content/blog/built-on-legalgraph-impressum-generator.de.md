---
title: "Gastartikel: ein Impressum-Vorlagen-Generator auf Basis von legalgraph"
description: legalgraph ist ein Datensatz, keine App. Wie Aimix darauf ein Browser-Werkzeug gebaut hat, das einer Website sagt, welche Impressumsregeln gelten, und die Vorlage schreibt, jede Zeile zurückverfolgbar bis in den Graphen.
published: 2026-11-11
author: Aimix
category: Auf legalgraph gebaut
---

*Ein Gastartikel von [Aimix](https://aimix.io), dem Unternehmen, das legalgraph begonnen hat und darauf
Produkte für kleine Unternehmen baut.*

legalgraph ist ein Datensatz. Er enthält amtliche Gesetzestexte, die darin markierten Vorschriften, die
Regeln, die diese Vorschriften begründen, und die Bedingungen, unter denen jede Regel gilt, alles als
offene Daten unter [CC BY 4.0](https://github.com/legalgraph-org/legalgraph/blob/main/LICENSE-DATA). Was er
bewusst nicht ist: eine App für eine bestimmte Aufgabe. Die [Checkliste](/de/checklist) auf dieser Website
zeigt, was die Daten beantworten können. Wer aber für seine Website ein Impressum braucht, braucht mehr als
eine Liste von Regeln: die Seite selbst.

Hier kommen Produkte ins Spiel. Dieser Artikel beschreibt eines davon, den
[Impressum-Vorlagen-Generator](https://aimix.io/de/impressum-template-generator) auf aimix.io, und wie er
den Graphen nutzt. Andere können dieselbe Art Werkzeug bauen: Alles, was er verwendet, steht unter
[Downloads](/de/download).

## Was der Generator tut

Besucher beantworten ein paar Fragen: wo das Unternehmen niedergelassen ist, ob die Website geschäftsmäßig
ist, wer sie betreibt, welche Registernummern es gibt, ob an Verbraucher verkauft wird. Mit jeder Antwort
erscheinen die Regeln, die gelten, einzeln, jede mit dem Grund, warum sie gilt, und der Vorschrift dahinter.
Am Ende steht das Impressum als Vorlage, auf Deutsch und Englisch für Deutschland und Österreich, auf
Ukrainisch und Englisch für die Ukraine, mit Platzhaltern wie FIRMENNAME statt der eigenen Angaben. Der
Generator fragt nach keinen personenbezogenen Daten, und die Vorlage entsteht im Browser.

## Wie er den Graphen nutzt

**Die Regeln kommen unverändert aus dem Graphen.** Einige SPARQL-Abfragen wählen die Impressumsregeln aus:
die Regeln zur [Anbieterkennzeichnung](/de/rules) und den Hinweis zur Verbraucherstreitbeilegung, in
Deutschland, Österreich, der EU und dem EWR, im Vereinigten Königreich und in der Ukraine. Sie liefern die
Regeln mit ihren Bedingungen, die zitierten Vorschriften mit ihren Zitaten und englischen Übersetzungen und
die Angaben, die jede Regel verlangt. Das Ergebnis ist eine JSON-Datei, die der Generator mitbringt. Ändert
sich der Graph, wird die Datei neu erzeugt; niemand bearbeitet eine Regel von Hand.

**Er gibt dieselben Antworten wie die Regel-Engine des Graphen.** legalgraph hat eine Regel-Engine, die
entscheidet, welche Regeln für eine Reihe von Tatsachen gelten. Der Generator hat eine kleine Kopie dieser
Logik im Browser. Damit beide nie auseinanderlaufen, werden beim Erzeugen der Datei ein Dutzend
Beispielunternehmen (eine deutsche GmbH, ein österreichischer Nachrichtenblog, ein ukrainischer
Onlineshop und so weiter) durch die Engine von legalgraph geschickt, und die Tests des Generators spielen
sie gegen seine eigene Logik nach.

**Jede Zeile verweist zurück.** Jede Regel im Ergebnis verlinkt auf ihre Seite auf dieser Website, etwa
[die deutsche Impressumsregel](/id/DE-R-impressum) oder [die EU-weite Regel](/id/EU-R-service-provider-information),
wo der zitierte Gesetzestext und seine amtliche Quelle einen Klick entfernt sind.

**Er sagt, was der Graph nicht weiß.** Wie gut der Generator ein Land abdeckt, wird aus dem Graphen
selbst ermittelt. Hat ein Land eigene Impressumsregeln im Graphen, sagt er das. Hat der Graph nur die
EU-weiten Regeln, mit oder ohne verlinkte Umsetzungsvorschrift des Landes, erfahren Besucher, dass
nationale Zusätze fehlen können, und bekommen die deutschen Regeln als strengen Maßstab angeboten. Hat der
Graph nichts, sagt er auch das, statt eine leere Liste zu zeigen, als gäbe es keine Regeln.

## Datensatz und Produkte: wer was tut

Die Trennung ist gewollt:

- **legalgraph** sammelt und prüft das Recht: amtliche Texte, gegen ihre Quellen geprüft, jede Regel
  zurückverfolgbar bis zu den Worten, aus denen sie stammt. Seine Regeln sind als Entwurf markiert, bis
  ein Anwalt sie geprüft hat, und sie sind eine Lesart des Rechts, keine Rechtsberatung.
- **Produkte** machen daraus etwas, das jemand für eine Aufgabe nutzen kann, mit eigenen Fragen,
  eigenem Wortlaut und eigener Gestaltung und mit eigener Verantwortung für das, was sie ihren Nutzern
  sagen.

Ein Produkt muss nie eine Regel kopieren oder erfinden. Korrigiert jemand hier eine Regel, bekommt jedes
auf dem Graphen gebaute Werkzeug die Korrektur mit seinem nächsten Update.

## Bauen Sie Ihr eigenes

Die Daten sind unter CC BY 4.0 frei nutzbar, mit einer Namensnennung wie *legalgraph by Aimix GmbH,
licensed under CC BY 4.0*. Unter [Downloads](/de/download) gibt es den Graphen in Turtle, N-Triples und
JSON-LD, und die [Methode](/de/method) erklärt, wie jede Regel entsteht. Wenn Sie etwas darauf bauen,
erzählen Sie es uns auf [GitHub](https://github.com/legalgraph-org/legalgraph): Wir würden es gern hier
aufführen.
