---
title: Warum wir legalgraph gebaut haben
description: Artikel über Website-Recht stellen Behauptungen auf. Wir wollten, dass jede Behauptung auf den Wortlaut des Gesetzes verweist, aus dem sie stammt.
published: 2026-11-07
category: Das Projekt
---

Aimix baut Websites für kleine Unternehmen. Jede dieser Websites muss sich an das Gesetz halten: Sie muss
angeben, wer sie betreibt, vor nicht notwendigen Cookies um Einwilligung bitten und Kunden ein Abo so leicht
kündigen lassen, wie sie es abgeschlossen haben. Als wir anfingen, für unsere Kunden über diese Pflichten zu
schreiben, stießen wir immer wieder auf dasselbe Problem. Zu sagen, was eine Website tun muss, war leicht.
Zu zeigen, woher das kommt, und zwar so, dass Leser es nachprüfen können, war schwer.

legalgraph ist unsere Lösung dafür. Wir veröffentlichen sie, damit andere das Problem nicht noch einmal lösen
müssen.

## Die Behauptung, die niemand prüfen kann

Wer ein paar Ratgeber zur Website-Compliance liest, findet Sätze wie diese:

- *Ins Impressum gehört die Umsatzsteuer-ID.*
- *Für Webanalyse braucht es eine Einwilligung.*
- *Ein Abo braucht einen Kündigungsbutton.*

Jeder davon stimmt ungefähr. Keiner sagt, welches Gesetz das verlangt, was genau darin steht, ob es für Sie
gilt und ob es heute noch so gilt. Die Quelle ist umschrieben, veraltet oder fehlt ganz. Wer sichergehen will,
hat zwei Möglichkeiten: dem Autor vertrauen oder das Gesetz selbst suchen und lesen.

Das Gesetz zu finden ist schwerer, als es klingt. Es steht in jedem Land auf einem anderen amtlichen Portal,
oft nur in der Landessprache, und eine Pflicht verteilt sich meist auf mehrere Vorschriften: Eine begründet
sie, eine zweite bestimmt, für wen sie gilt, eine dritte legt das Bußgeld fest.

## Was zu einer Behauptung gehört

Wir haben entschieden, dass jede Aussage, die wir über Website-Recht machen, ihren Beleg mitbringen muss.

### Der Wortlaut des Gesetzes

Keine Zusammenfassung des Gesetzes, sondern die Vorschrift selbst, wörtlich zitiert aus dem Text, den das
amtliche Portal veröffentlicht. Die Originaldatei wird unverändert aufbewahrt, mit ihrem Hashwert und dem
Datum des Downloads, sodass jeder sie erneut abrufen und vergleichen kann. Die [Methode](/de/method) beschreibt,
wie jedes Zitat maschinell gegen diese Datei geprüft wird, damit es sich nicht unbemerkt vom
veröffentlichten Text entfernen kann.

### Eine Übersetzung, die sagt, was sie ist

Das meiste Website-Recht Europas gibt es nicht auf Englisch. Wo es eine amtliche englische Fassung gibt,
verwenden wir sie und sagen das. Wo nicht, ist das Englische eine maschinelle Übersetzung, als solche
gekennzeichnet, und bleibt ein Entwurf, bis ein Mensch sie geprüft hat. Nichts, was wir selbst geschrieben
haben, wird als amtlicher Text ausgegeben.

### Wer es geprüft hat, und wie weit

Jede Vorschrift trägt einen Prüfstatus. *Source checked* heißt, ihr Wortlaut wurde mit dem amtlichen Text
verglichen. *Draft* heißt, das ist noch nicht geschehen. Dasselbe gilt für unsere Lesart des Gesetzes: Eine
Regel beginnt als Entwurf und bleibt es, bis eine Anwältin oder ein Anwalt sie geprüft hat.

## Eine Behauptung, bis zur Quelle verfolgt

Nehmen wir die erste Behauptung oben, etwas genauer gefasst: *Eine geschäftsmäßige deutsche Website muss
ihre Umsatzsteuer-Identifikationsnummer angeben, wenn sie eine hat.* In legalgraph ist das eine Regel,
[Impressum: VAT identification number](/id/DE-R-impressum-vat), und sie sagt, wann sie gilt: Das Unternehmen
ist in Deutschland niedergelassen, betreibt eine geschäftsmäßige Website und hat eine Umsatzsteuer-ID.

Die Regel verweist auf die Vorschrift, aus der sie stammt, [§ 5 Abs. 1 DDG](/id/DE-DDG-s5-1), das
Digitale-Dienste-Gesetz. Dort steht Nummer 6 dieses Absatzes im deutschen Original, mit der englischen
Übersetzung daneben. Die Vorschrift verweist auf [die Datei von gesetze-im-internet.de](/id/DE-DDG-source),
gegen die das Zitat geprüft wurde.

An der Grenze endet die Spur nicht. Die deutsche Pflicht setzt [Artikel 5 der
E-Commerce-Richtlinie](/id/EU-R-service-provider-information) um. Ein Unternehmen in Österreich oder
Frankreich hat also dieselbe Pflicht, nach dem Recht seines eigenen Landes, und der Graph nennt auch dieses
Gesetz.

Drei Klicks, von einer Behauptung bis zu den Worten, die sie begründen. Das ist die ganze Idee.

## Warum offene Daten und ein eigenes Projekt

Wir hätten das als internes Werkzeug behalten können. Stattdessen veröffentlichen wir es als offene Daten
unter CC BY 4.0, aus zwei Gründen.

Erstens wird eine Behauptung erst prüfbar, wenn der Beleg öffentlich ist. Wer über Website-Recht schreibt,
ein Compliance-Werkzeug baut oder das Thema unterrichtet, kann auf einen Eintrag verlinken, statt ihn zu
umschreiben, und die Leser können dem Link folgen.

Zweitens funktionieren Links nur, wenn sie bleiben. Jeder Eintrag im Graphen hat eine dauerhafte Adresse,
etwa `legalgraph.org/id/DE-DDG-s5-1`. Sobald Artikel, Daten und Werkzeuge anderer auf eine Adresse
verweisen, darf sie sich nie mehr ändern. Eine eigene Domain, getrennt von der Marke eines Unternehmens,
hält diese Adressen stabil und erlaubt Juristinnen und Juristen, Forschenden und Behörden, zu einem neutralen
Projekt beizutragen. Die Artikel und Produkte von Aimix nutzen den Graphen wie alle anderen auch.

## Was es nicht ist

legalgraph ist strukturierte Recherche von Forschenden, nicht von Anwälten. Es ist keine Rechtsberatung und
ersetzt keine. Es macht den Ausgangspunkt sichtbar: welche Vorschrift, welcher Wortlaut, welche Fassung und
wie sicher wir uns bei jedem davon sind.

## Ausprobieren

- Die [Checkliste](/de/checklist) macht aus wenigen Angaben zu einem Unternehmen die Regeln, die für es gelten,
  jede mit ihren Quellen.
- [Länder](/de/countries) zeigt, wie viel vom Website-Recht jedes Landes bisher im Graphen ist.
- [Gesetzestexte](/de/sources) listet jedes Original mit seinem Hashwert, und die Daten lassen sich vollständig
  herunterladen.

Wenn Sie eine falsche Lesart, einen veralteten Text oder ein fehlendes Gesetz finden, [eröffnen Sie ein Issue
auf GitHub](https://github.com/legalgraph-org/legalgraph/issues) oder [schreiben Sie uns](mailto:contact@aimix.io). Jede Aussage im Graphen ist eine
Anmerkung zum Wortlaut des Gesetzes selbst, eine Korrektur ist also eine kleine Änderung, die jeder nachprüfen
kann. [Wie Sie zu legalgraph beitragen](/de/blog/how-to-contribute) erklärt den Rest.
