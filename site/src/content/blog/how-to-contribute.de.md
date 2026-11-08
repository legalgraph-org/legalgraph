---
title: Wie Sie zu legalgraph beitragen
description: Der Graph wächst mit jedem Gesetz, jedem Land und jeder Gerichtsentscheidung, die jemand hinzufügt. Wie ein Beitrag abläuft, vom Issue bis zum geprüften Pull Request, und wohin das alles führt.
published: 2026-11-07
category: Das Projekt
---

legalgraph wird nie von einem einzelnen Team fertiggestellt. Es gibt Hunderte von Gesetzen, die einer
Website vorschreiben, was sie zeigen und tun muss, in Dutzenden von Ländern und Sprachen, und Gerichte
und Behörden legen sie jeden Monat neu aus. Der Graph ist so gebaut, dass jeder, der einen Teil dieses
Rechts kennt, ihn hinzufügen kann, und jeder andere prüfen kann, was hinzugefügt wurde.

Dieser Artikel zeigt, wie das funktioniert. Die Befehle stehen im
[Leitfaden für Beiträge](https://github.com/legalgraph-org/legalgraph/blob/main/CONTRIBUTING.md) auf GitHub.

## Was Sie hinzufügen können

Der Graph ist darauf angelegt, in drei Richtungen zu wachsen.

### Mehr Gesetze

Das Datenschutzgesetz eines Landes, eine Vorschrift zur Preisangabe, die Pflicht, eine
Verbraucherschlichtungsstelle zu nennen: Jedes davon ist ein Gesetzestext auf einem amtlichen Portal. Sie
fügen den Text so hinzu, wie das Portal ihn veröffentlicht, markieren die Absätze, auf die es ankommt,
und der Graph wird aus Ihren Markierungen erzeugt. Niemand tippt ein Zitat von Hand ab, also muss auch
niemand einem Zitat einfach glauben. Die [Methode](/de/method) zeigt den ganzen Weg an einer Pflicht als
Beispiel.

### Mehr Länder

Der Graph umfasst die EU und den größten Teil Europas, das Vereinigte Königreich, die Ukraine, die USA
und Kalifornien, aber unterschiedlich tief. Für manche Länder stammt jede Vorschrift aus dem amtlichen
Text, für andere sind die Einträge noch Entwürfe aus Recherchenotizen. Ein Land von Entwürfen auf seine
amtlichen Texte umzustellen, ist einer der wertvollsten Beiträge überhaupt, und dafür braucht es
jemanden, der das Recht dieses Landes in seiner eigenen Sprache liest.

### Mehr Gerichtsentscheidungen

Das Gesetz sagt, was eine Website tun muss. Entscheidungen zeigen, was passiert, wenn sie es nicht tut:
eine Unterlassung wegen eines Cookie-Banners, ein Bußgeld für Cookies ohne Einwilligung, Schadensersatz
für eine eingebundene Schriftart. Jede Entscheidung im Graphen hält ihr Ergebnis fest, gegen wen sie
erging, wegen welcher Vorschrift, und die Stelle des Urteils, die das sagt, sodass man es am Wortlaut
der Entscheidung prüfen kann.

## Wie ein Beitrag abläuft

### 1. Mit einem Issue beginnen

Sie haben ein falsches Zitat gefunden, ein geändertes Gesetz oder eine Übersetzung, die den Sinn
verfehlt? [Eröffnen Sie ein Issue](https://github.com/legalgraph-org/legalgraph/issues) auf GitHub, mit
einem Link auf den amtlichen Text. Schon das ist ein Beitrag: Jemand kann es beheben, und alle sehen,
dass es bekannt ist.

Wenn Sie etwas Größeres vorhaben, etwa ein neues Land oder eine neue Art von Entscheidung, eröffnen Sie
ebenfalls zuerst ein Issue. So einigen wir uns auf den Umfang, bevor Sie Zeit investieren.

### 2. Der Ontologie folgen, oder sie erweitern

Alles im Graphen folgt einem gemeinsamen Modell, der Ontologie: was ein Rechtsakt ist, was eine
Vorschrift ist, was es heißt, dass eine Vorschrift eine Angabe *verlangt*, was eine Regel und ihre
Bedingungen sind. Neue Daten verwenden die Begriffe, die es schon gibt. Das macht eine deutsche und eine
französische Vorschrift vergleichbar und eine Abfrage über alle Länder zugleich möglich.

Manchmal fehlt der Begriff, den Sie brauchen, weil ein Gesetz etwas verlangt, das kein anderes Gesetz
im Graphen verlangt. Dann fügen Sie ihn im selben Pull Request der Ontologie hinzu, mit einer englischen
Definition, die das Gesetz wiedergibt. Eine Prüfung weist jeden Begriff zurück, der nicht definiert ist,
sodass Daten und Modell nicht auseinanderlaufen. Änderungen am Modell selbst, etwa neue Arten von Dingen
oder Beziehungen, besprechen wir zuerst in einem Issue, weil sie jedes Land betreffen.

### 3. Einen Pull Request eröffnen

Die Änderung geht als Pull Request an GitHub. Vorher prüft ein einziger Befehl alles, was eine Prüferin
oder ein Prüfer geprüft haben möchte: die Gesetzestexte gegen ihre Originale, die erzeugten Daten gegen
die annotierten Texte, den Graphen gegen die Regeln der Ontologie und die Beispielunternehmen gegen die
Regeln, die für sie gelten müssen.

Dann liest jemand aus dem Kreis der Maintainer den Beitrag, wie eine Juristin oder ein Jurist einen
Schriftsatz liest: Stimmt das Zitat mit dem amtlichen Text überein, sitzt die Markierung am richtigen
Absatz, folgt die Regel aus den Vorschriften, die sie nennt? Wo Sie das Gesetz ausgelegt statt zitiert
haben, sagt der Pull Request das, und der Eintrag bleibt ein Entwurf, bis eine fachkundige Person ihn
geprüft hat.

## Vom Beitragenden zum Maintainer

Maintainer prüfen Änderungen am Graphen und nehmen sie an. Heute ist das das Team, das ihn begonnen hat.
Wir möchten, dass es wächst: Wer über längere Zeit substanziell und sorgfältig beiträgt, kann eingeladen
werden, Maintainer zu werden und mitzuentscheiden, was in den Graphen aufgenommen wird. Das Recht eines
Landes oder seine Portale zu kennen, zählt dabei so viel wie Code zu schreiben.

## Wohin das führt

Das Ziel ist ein Graph, der vollständig genug ist, dass Unternehmerinnen und Unternehmer sehen, welche
Regeln für ihr Unternehmen am meisten zählen: wo es niedergelassen ist, wo es verkauft, was seine
Website tut. Jede Regel kommt mit dem Gesetz, aus dem sie folgt, im Originalwortlaut und auf Englisch.

Das ist keine Rechtsberatung, und der Graph gibt auch nie vor, es zu sein. Regeln sind unsere Lesart des
Gesetzes und bleiben als Entwurf gekennzeichnet, bis eine Anwältin oder ein Anwalt sie geprüft hat. Ihr
Zweck ist Bewusstsein. Zu viele Unternehmen erfahren von einer Pflicht erst durch eine Abmahnung. Das
Gesetz ist öffentlich, und Informationen darüber, was es verlangt, sollten ebenso offen und zugänglich
sein, statt hinter Bezahlschranken zu liegen oder bis zur Unkenntlichkeit umschrieben zu werden.

## Auch für KI-Agenten gebaut

Immer mehr Menschen fragen zuerst einen KI-Assistenten. Ein Assistent, der aus dem Gedächtnis antwortet,
umschreibt, und kann veraltet oder schlicht falsch liegen. Einer, der den Graphen lesen kann, kann
nachsehen, welche Regeln für ein Unternehmen gelten, die Vorschrift dahinter zitieren und auf sie
verlinken, sodass seine Antwort Quellen hat, die ein Mensch prüfen kann.

Damit wird der Graph zum Ausgangspunkt für Agenten, die eine erste Recherche übernehmen: eine erste
Karte der Regeln, auf die es ankommt, der Unternehmerinnen und Unternehmer, oder ihre Anwälte, dann bis
zum Gesetz selbst folgen können. Jeder Beitrag macht diese Karte vollständiger, für Menschen wie für
Agenten.

## Hier anfangen

- Das Repository: [github.com/legalgraph-org/legalgraph](https://github.com/legalgraph-org/legalgraph).
  Vergeben Sie einen Stern, klonen Sie es und führen Sie `make check` aus.
- [CONTRIBUTING.md](https://github.com/legalgraph-org/legalgraph/blob/main/CONTRIBUTING.md): der
  praktische Leitfaden, von der Einrichtung bis zum ersten Gesetz (auf Englisch).
- [Issues](https://github.com/legalgraph-org/legalgraph/issues): melden Sie, was falsch ist, oder
  schlagen Sie vor, was fehlt.
- Die [Methode](/de/method) und das [Glossar](/de/glossary), falls RDF, Turtle und SPARQL neu für Sie sind.
