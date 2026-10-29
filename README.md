# AURUM · Lokale Trading-KI für MT5-Demokonten

Ein experimentelles Windows-System mit lokalen Sprachmodellanalysen, begrenzter Strategieforschung, mehreren Kursmodellen, Lernjournal und automatischem XAUUSD-Demohandel. **Keine umfassende selbstständig denkende Intelligenz, kein Profitabilitätsnachweis, kein Echtgeldmodus.**

## Einrichtung auf deinem Windows-PC

Für 32 GB RAM und eine RTX 4070 ist zunächst **Qwen2.5 7B über Ollama** vorgesehen. Inferenz läuft lokal; das Modell ist mehrere GB groß. Eine aktuelle Ollama-Installation und funktionierende NVIDIA-Treiber sind erforderlich. Die konkrete Windows-/GPU-Ausführung muss auf deinem PC geprüft werden.

1. Python **3.12, 64-bit**, inklusive Python Launcher installieren.
2. MT5 öffnen, Demokonto anmelden und XAUUSD einblenden. Falls Gold anders heißt, `symbol` in `config.json` anpassen. Manche MetaQuotes-Demoserver bieten kein Gold an; dafür ist ein Broker-Demokonto mit Gold erforderlich.
3. Algorithmischen Handel in MT5 zulassen. Unter Extras → Optionen → Expert Advisors die Sperre für automatischen Handel über die externe Python-API ausschalten. Algo Trading aktivieren.
4. `setup_local_ai.bat` ausführen. Fehlt Ollama, öffnet sich die offizielle Windows-Downloadseite. Ollama installieren/starten und die Datei danach erneut ausführen. Sie lädt `qwen2.5:7b` und testet das lokale Modell.
5. `local_ai.json` prüfen: Slippage und Kommission an deinen Broker anpassen. `commission_per_lot_round_trip` ist die Gesamtkommission für Eröffnung und Schließung eines Lots in Kontowährung. **0 ist eine Nullkostenannahme**, keine automatisch ermittelte Brokergebühr.
6. `start.bat` ausführen. Das Browser-Dashboard läuft auf http://127.0.0.1:8765. Das Konsolenfenster offen lassen. Falls sich der Browser zu früh öffnet, die Seite nach Dienststart neu laden.
7. Unter **Lokale Trading-KI** die Quellenanalyse und Forschungsergebnisse prüfen. Der erste Modellstart kann einige Minuten dauern. Forschung und Kursmodelltraining laufen auch bei pausiertem Demohandel. Der Autopilot ist bei einer neuen Installation bereits angefordert. Er handelt automatisch, sobald die Daten und sämtliche Prüfungen bereit sind. Ein zuvor manuell gespeicherter Stopp bleibt bestehen.

Der Autopilot ist beim ersten Start standardmäßig aktiviert. **Autopilot stoppen** speichert deinen Stopp dauerhaft; erst **Autopilot aktivieren** hebt ihn wieder auf. Fehlen Ollama, Nachrichtenquellen oder bestandene Prüfungen, handelt sie standardmäßig nicht. Ein pausierter/gesperrter Bot ist kein Beleg für einen Programmfehler; die Oberfläche zeigt den jeweiligen Grund.

## Update einer vorhandenen Installation

1. Neue Einstiege stoppen und die Python-Konsole schließen. Offene Positionen in MT5 kontrollieren.
2. Die aktuelle GitHub-ZIP in einen **neuen Ordner** entpacken.
3. Aus dem bisherigen Ordner `config.json`, `account.json`, `trades.sqlite` sowie gegebenenfalls `research.sqlite` und deine angepasste `local_ai.json` in den neuen Ordner übernehmen. Vorher eine Sicherung anlegen. Eine neue Datei `local_ai.json` liegt der ZIP für die erste lokale KI-Einrichtung bei.
4. Die lokale KI wie oben einrichten, anschließend `start.bat` im neuen Ordner starten. Nicht beide Instanzen parallel betreiben. Im Browser **Strg+F5** drücken.

So werden neue Python-Module vollständig übernommen, während deine Daten erhalten bleiben. Ein altes Programm nur durch Austausch von `app.py` zu aktualisieren reicht für diese Version nicht aus.

## Vollautomatischer Betrieb

Nach einmaliger Einrichtung startet `start.bat` die benötigte lokale Ollama-Instanz, falls sie nicht bereits läuft, und AURUM. Die MT5-Python-Anbindung versucht, das installierte Terminal zu initialisieren; dein vorbereitetes Demokonto muss dort verfügbar sein. Bei mehreren MT5-Installationen muss das richtige Terminal gewählt/offen sein. Zugangsdaten werden von AURUM nicht verwaltet.

Der Autopilot ist bei einer neuen Datenbank bereits angefordert. Sobald MT5-Demokonto, aktuelle Daten, Modellprüfung, Strategieforschung, Risikolimits und Signalbestätigungen bereit sind, eröffnet er Demo-Orders selbstständig. Es ist keine Einzelbestätigung je Trade nötig. Nach vorübergehenden Verbindungsfehlern oder Marktpausen versucht der Dienst die Verbindung weiter und wird automatisch wieder bereit. Ein **manueller Stopp bleibt über Neustarts gespeichert**. Kursmodelltraining und Forschungsanalyse können während eines manuellen Handelsstopps weiterlaufen.

Mit `enable_autostart.bat` wird eine Verknüpfung für deinen Benutzer im Windows-Autostart angelegt. AURUM startet dann nach der **Windows-Anmeldung**, nicht bereits vor der Anmeldung. Erst Einrichtung und Modelltownload abschließen, dann Autostart aktivieren. Den Programmordner anschließend nicht verschieben. `disable_autostart.bat` entfernt die Verknüpfung; einen laufenden Dienst beendet das nicht. Falls Windows die PowerShell-Ausführung durch eine Organisationsrichtlinie verhindert, kann die Verknüpfung nicht angelegt werden.

Der PC muss eingeschaltet und wach bleiben, Ollama und MT5 müssen erreichbar sein. Bei ausgeschaltetem PC oder Energiesparmodus erfolgen keine Analysen und keine neuen Orders. Der Autostart ist kein Windows-Dienst und kein Prozess-Watchdog: Ein abgestürzter oder beendeter Python-Prozess wird nicht automatisch innerhalb derselben Sitzung neu gestartet.

### Dauerhaftes Lernen und automatische Pausen

- Kursmodelle trainieren stündlich aus den verfügbaren Kursdaten und älteren abgeschlossenen Trade-Ergebnissen. Neue Daten können die Gewichte verändern; identische Daten können identische Ergebnisse liefern.
- Die lokale KI aktualisiert Quellenanalysen und ruft frühere Forschungsberichte ab. Unabhängige Strategietests erfolgen erst mit genügend neuen Testkerzen. Sprachmodellgewichte werden dabei nicht feintrainiert.
- Fehlende Daten, unzureichende Modelle und Risikosperren verhindern Einstiege, während verfügbare Analysefunktionen weiterarbeiten. Automatisch bedeutet nicht, dass Trades erzwungen werden.
- Vor einem Orderversuch wird die Symbol-/Zeitebenen-/Kerzenkombination dauerhaft gespeichert. Nach Neustarts erfolgt kein zweiter Versuch für dieselbe Kombination.
- Ist unklar, ob eine Order vom Broker angenommen wurde (etwa Zeitüberschreitung), erfolgt ein gespeicherter Halt statt einer automatischen Wiederholung. Das schützt vor Doppelorders. Die Oberfläche fordert dann zur MT5-Prüfung und ausdrücklichen Reaktivierung auf. Dieses Prüfen bleibt eine Ausnahme vom unbeaufsichtigten Betrieb.

## Was die einzelnen Teile leisten

### Lokales Sprachmodell

Die App spricht ausschließlich `http://127.0.0.1:11434` an und umgeht dafür HTTP-Proxys. Kein externer Sprachmodell-Dienst wird verwendet. Das Modell erhält öffentliche Marktdaten, Quellen und frühere Forschungsberichte, keine MT5-Zugangsdaten oder Kontonummern.

Die Nachrichtenanalyse verwendet Titel und verfügbare Zusammenfassungen datierter öffentlicher RSS-Meldungen von Federal Reserve und BLS. Sie zeigt Links, Veröffentlichungszeiten, mögliche wirtschaftliche Zusammenhänge, Unsicherheiten und eine Modellbewertung des Risikos. Ältere Meldungen werden als Hintergrund gekennzeichnet. Fehlgeschlagene Quellen werden angezeigt. **Kein vollständiger Nachrichtenstrom, kein Wirtschaftskalender, keine Überraschungsdatenbank und kein garantiert sachlich korrektes Verständnis.** Belegte Quellenbezüge verringern erfundene Quellen, beweisen aber nicht die Richtigkeit jeder Aussage. Ein Modellergebnis bleibt eine Interpretation.

Das vortrainierte Sprachmodell wird hier **nicht feintrainiert**. Gespeicherte Forschungsberichte werden gezielt als Kontext abgerufen. Das ist Erfahrungsabruf, keine automatische Änderung seiner Sprachmodellgewichte.

### Strategieforschung und Auswahl

Das Sprachmodell darf neue Parameter für drei vorgegebene Regelfamilien vorschlagen: Momentum, Gegenbewegung und Ausbruch. Es darf keinen frei erzeugten Code ausführen. Parameter werden streng geprüft. Es entwickelt damit prüfbare Hypothesen innerhalb eines begrenzten Suchraums, keine beliebigen neuen Handelsalgorithmen.

Für die Ausführungszeitebene werden bis zu 4.000 Kerzen geladen; mindestens 1.000 sind erforderlich. Die ersten 60 % dienen als Entwicklungskontext für den Strategieaufruf, die nächsten 20 % als Validierung und die letzten 20 % als abschließender Test. Der Strategieaufruf erhält weder diese Testkurse noch heutige Nachrichten. Die aktuelle Nachrichtenanalyse ist ein **getrennter** Sprachmodellaufruf. Die Tests belegen daher ausschließlich die technischen Regeln, nicht die Profitabilität nachrichtenbasierter Entscheidungen.

Kandidat und bisherige Referenz werden auf denselben Abschnitten geprüft. Eingänge werden am nächsten Kerzen-Open simuliert. Berücksichtigt werden historische Bid/Ask-Spreads, eine Slippage-Annahme und die konfigurierte Kommission. Bei einer Kerze, die Stop und Ziel berührt, wird konservativ der Stop zuerst gewertet. Stop-Gaps können mehr als ein geplantes Risiko verlieren.

Die Ausgabe wird in R dargestellt: Ein R entspricht dem geplanten Stop-Risiko. Die festen Forschungsschranken sind mindestens 30 abgeschlossene Test-Trades je Abschnitt, positives Nettoergebnis, mindestens 0,05 R pro Trade im Mittel und höchstens 10 R Drawdown. Ein Kandidat ersetzt die Referenz nur, wenn er beide Abschnitte besteht und die Referenz jeweils im Nettoergebnis übertrifft. Besteht lediglich die Referenz, bleibt sie ausgewählt. Besteht keine, werden neue Einstiege gesperrt. Das sind Forschungsschranken, **kein statistischer Beweis eines Vorteils**.

Weitere unabhängige Strategietests benötigen einen vollständig neuen letzten Testabschnitt nach den zuvor geprüften Kerzen. Die KI optimiert nicht stündlich gegen denselben Test und bezeichnet das als neuen Erfolg. Bis genug neue Kerzen vorliegen, werden nur Nachrichten aktualisiert. Prüfungen verfallen nach `max_strategy_age_hours` (Standard 48 Stunden); das kann zusätzliche Pausen verursachen. Höhere Zeitebenen benötigen für neue Tests sehr lange Zeit. Preis- und Nachrichteninformationen, die schon im vortrainierten Modell enthalten waren, lassen sich nicht vollständig aus seinem Vorwissen entfernen; echte zukünftige Demodaten bleiben für die Validierung wichtig.

Kostenänderungen sperren neue Einstiege, bis eine neue Prüfung stattgefunden hat. Eine spätere erneute Prüfung kann die bisherige Strategie verwerfen. Die Ergebnisse aller Läufe werden gespeichert. Ein automatisches Zurücksetzen anhand realer Live-Trade-Statistiken sowie vollständige Walk-forward-Portfolio-Tests sind noch nicht implementiert.

### Automatischer Demohandel

Die bestehenden Kursmodelle werden je Zeitebene trainiert. Standard: M1, M5, M15, M30, H1, H4 und D1. Es müssen keine zusätzlichen Charts geöffnet sein. Mindestens 800 geschlossene Kerzen pro Kursmodell sind nötig. Andere native MT5-Zeitebenen sind in `timeframes` konfigurierbar. M5 bleibt standardmäßig die Ausführungszeitebene (`execution_timeframe`).

Das Ausführungsmodell benötigt mindestens 55 % Balanced Accuracy auf seinem historischen Test und eine Richtungsschätzung oberhalb 65 % bzw. unterhalb 35 %. Mindestens zwei geprüfte Modelle müssen die Richtung stark bestätigen, starke Gegensignale sperren. Die Wahrscheinlichkeitsschätzungen sind nicht kalibriert. Diese Richtungsprüfung ist kein Profitabilitätsnachweis.

Zusätzlich muss die lokale Forschungsstrategie bei `require_research_for_entries: true` denselben Einstieg bestätigen, ihre Prüfung aktuell sein und die Nachrichtenanalyse darf kein erhöhtes Risiko melden. `unknown` bedeutet unbekannt, nicht risikofrei. Die Forschungsstrategie darf die ursprünglichen Risikosperren nicht aufheben. SL-/TP-Abstände stammen aus ihren geprüften Regeln; das Mindestabstandslimit des Brokers kann sie verändern. Eigene so eröffnete Positionen erhalten außerdem einen Zeitausstieg nach der vorgeschlagenen Zahl geschlossener Kerzen. Dieser Zeitausstieg benötigt einen laufenden Dienst. Bereits übermittelte SL/TP liegen in MT5/Broker.

Das Demokonto wird vor Orders geprüft, Kontowechsel werden gesperrt. Höchstens eine Position pro Symbol, geplantes Risiko 0,25 % der Equity je Einstieg, Tagesverlustsperre 2 % gegen die erste gespeicherte Equity des UTC-Tages. Kontoweite Equity enthält auch manuelle Trades, Ein-/Auszahlungen und offene Verluste. Die Tagesgrenze sperrt neue Einstiege und liquidiert nicht automatisch. **Kein garantiertes Verlustmaximum.**

**Autopilot stoppen** lässt Positionsverwaltung und SL/TP aktiv. Vorübergehende Verbindungsprobleme sperren Einstiege; nach Wiederherstellung wird ein angeforderter Autopilot automatisch wieder bereit. Ein unklarer Orderstatus führt zu einem dauerhaft gespeicherten Halt. Dann MT5 prüfen und den Autopiloten ausdrücklich neu aktivieren. Offene Positionen bei Bedarf direkt in MT5 schließen. Änderungen von Symbol und Zeitebenen nur ohne offene Bot-Positionen vornehmen. Eine Installation gehört zu einem Konto.

### Lotgröße selbst im Dashboard wählen

Im Bereich **Positionsgröße einstellen** den Modus wählen, bei **Feste Lotgröße** zum Beispiel `0,10`, `0.10` oder `1,00` eingeben und **Lot-Einstellung speichern** anklicken. Gespeichert wird in `trades.sqlite`; die Auswahl bleibt beim Neustart erhalten und wird von der KI nicht verändert. Sie gilt ab dem nächsten neuen Trade. Offene Positionen werden nicht umskaliert.

Im Modus **Automatisch nach Risikobudget** bleibt die bisherige risikobasierte Berechnung aktiv. Im Modus **Feste Lotgröße** bestimmt deine Eingabe die Positionsgröße anstelle des automatischen Risikobudgets je Trade. Dadurch kann das Stop-Risiko höher als die eingestellten 0,25 % sein. Der geschätzte Verlust am aktuellen Stop und der Anteil an der Equity werden angezeigt; Gebühren, Slippage und Kurslücken sind in dieser Vorschau nicht enthalten. Es handelt sich nicht um eine Verlustgarantie oder um die Zusage eines bevorstehenden Einstiegs.

Mindestlot, Höchstlot und Schrittweite des Brokers werden angezeigt und validiert, sobald MT5-Daten verfügbar sind. Ungültige Werte werden nicht automatisch gerundet. Ohne Verbindung lässt sich ein positiver Wert vormerken; vor einer Order wird er gegen die aktuellen Brokergrenzen geprüft. Tagesverlustgrenze, Demokontoprüfung, Modell-/Strategieprüfungen, Stop-Loss und Marginprüfung bleiben aktiv. Der neue Bereich erfordert die aktuelle `app.py`, das neue Modul `sizing.py` und die aktuelle `static/index.html`; am einfachsten den vollständigen ZIP-Ordner nach der Update-Anleitung verwenden.

### No-Trading-Zonen

In `config.json`:

- `price_zones`: z. B. `[[2700,2715],[2750,2760]]`, absolute Preiszonen.
- `blocked_hours_utc`: gesperrte ganze UTC-Stunden; Sommer-/Winterzeit berücksichtigen.
- `blocked_windows_utc`: z. B. `[["2026-11-06T13:15:00+00:00","2026-11-06T14:15:00+00:00"]]`, manuelle Ereignissperren.
- `max_spread_atr`: maximaler Spread relativ zur ATR, Standard 0,12.

Ein automatischer Kalender mit Sperren vor kommenden Nachrichten ist noch nicht angeschlossen. Eine Analyse bereits veröffentlichter RSS-Texte ersetzt diesen nicht.

## Prüfen, ob MT5 überhaupt Orders annehmen kann

Unter **MT5-Verbindung praktisch testen** gibt es eine bewusst manuelle Diagnose: **Demotest: kleinste Kaufposition eröffnen und schließen**. Ein Klick stoppt den Autopiloten dauerhaft, prüft Demokonto, Kontobindung, freie Positionen/Orders im Symbol, aktuelle Kurse, Broker-Mindestlot, Test-Risikobudget, Tagesverlustgrenze und MT5-Orderprüfung. Dann wird genau ein Kaufversuch mit SL/TP gesendet und die zugehörige Testposition unmittelbar wieder geschlossen. Bei bekannter Position wird nur deren Ticket zum Schließen verwendet.

Der Test ignoriert KI-Einstiegsregeln und manuelle Zeit-/Preiszonen, damit die technische Orderverbindung unabhängig davon prüfbar ist. Er verwendet nicht die gespeicherte feste Lotgröße. Testtrades haben eine separate Kennzeichnung und gelangen nicht in das Kursmodelltraining. Es können Spread und Gebühren im Demokonto anfallen.

Das Ergebnis zeigt die einzelnen Schritte, Orderticket und MT5-Rückmeldungen. **Eröffnen und Schließen bestätigt** beweist nur die technische Verbindung auf deinem Konto. Markt geschlossen, Handelsfreigabe fehlt, ungültige Brokerparameter oder unklare Antworten erscheinen als Fehler. Ein nicht eindeutig bestätigtes Ergebnis wird nicht als Erfolg angezeigt und nicht automatisch erneut eröffnet. Wenn die Position nicht als geschlossen bestätigt ist, direkt in MT5 prüfen und bei Bedarf manuell schließen. Erst nach eigener Prüfung und ohne offene Positionen/Orders im Symbol lässt sich ein ungeklärter Teststatus über den entsprechenden Button zurücksetzen. Zwischen Versuchen liegen mindestens 60 Sekunden.

Der Autopilot bleibt nach dem Test gestoppt. **Autopilot aktivieren** startet anschließend wieder die normale Strategieausführung mit allen bisherigen Filtern. Im Testbereich stehen außerdem die gemeldeten Einstiegssperren des laufenden Datenzyklus. Sie erklären, warum die Strategie aktuell nichts eröffnet. Ein bestandener Verbindungstest entfernt diese Sperren nicht.

Für dieses Update die aktuelle `app.py`, das neue Modul `demo_test.py` und den Ordner `static` in den bisherigen Programmordner übernehmen oder die vollständige ZIP nach der allgemeinen Update-Anleitung verwenden. Dann Dienst neu starten und im Browser Strg+F5 drücken. Frühere Testprotokolle werden in `trades.sqlite` gespeichert, nicht als simulierte Broker-Erfolge erfunden. Die automatisierten Tests verwenden ein simuliertes Terminal; der reale Verbindungsnachweis entsteht erst beim Klick auf deinem Windows-PC.

## Wo du das Lernen siehst

**Lokale Trading-KI:** Quellenanalyse, Hypothese, Kandidat/Referenz, Handelskosten, Test-Trades, Netto-R, Drawdown, Freigabe und letzte Forschungsberichte. Das funktioniert erst nach erfolgreicher lokaler Einrichtung und verfügbarer Datenverbindung.

**Analyse nachvollziehen:** tatsächliche Beiträge der vier Kursmerkmale zum logistischen Richtungsmodell. Das sind Modellberechnungen, keine kausalen Erklärungen künftiger Kurse.

**Lernjournal:** Zeitpunkt, Modellversion je Zeitebene, verwendete Kurs-/Trade-Beispiele, Gewichte, Änderungen und historische Testergebnisse. Null Trade-Beispiele heißt, dass kein Trade-Ergebnis in diesen Trainingslauf eingegangen ist. Nur ausreichend alte abgeschlossene Bot-Trades ergänzen das Training, damit der Testzeitraum getrennt bleibt. Trainingsläufe werden stündlich durchgeführt. Jede zusätzliche Erfahrung kann hilfreich oder irreführend sein und garantiert keine Verbesserung.

Ältere Trades ohne getrennte Merkmale ergänzen nur M5. Das Journal beginnt mit der Version, die es eingeführt hat. Frühere ungespeicherte Läufe werden nicht erfunden. Die Kursmodelle werden beim Neustart neu trainiert; alte Parameter sind protokolliert, werden aber noch nicht automatisch als aktive Modelle wiederhergestellt.

## Daten und technische Grenzen

- `trades.sqlite`: Trade-Journal, Kursmodell-Lernjournal, Tagesbasis und Forschungs-Zeitausstiegspläne.
- `research.sqlite`: lokale KI-Analysen, Quellen, Hypothesen, Prüfungen und Referenzentwicklung.
- `account.json`: lokale Kontobindung, keine Zugangsdaten.
- `local_ai.json`: lokales Modell, Quellen, Kostenvorgaben und Forschungseinstellungen.

Das Dashboard lauscht nur auf 127.0.0.1 und schützt Schreibaktionen mit einem Sitzungstoken. News-Downloads benötigen Internet; die Inferenz läuft lokal. RSS-Verfügbarkeit und Modellqualität können schwanken. Keine Garantie, dass jeder Vorschlag gültiges JSON liefert; ungültige Antworten werden angezeigt und verworfen.

Die Simulation ist vereinfacht: keine vollständige Margin-/Lot-Rundungs-/Latenz-/Liquiditäts-/Portfolio-Simulation, keine detaillierten Broker-Fill-Regeln, keine Intrabar-Tickdaten. Reale MT5-Ausführungen können abweichen. Positionsgröße, Mindestabstände und Multi-Zeitebenenfilter verändern die tatsächlichen Trades gegenüber dem isolierten Strategietest. Forschungsergebnisse sind daher kein Nachweis der Profitabilität des kombinierten Systems.

## Entwicklungstests

`python -m unittest discover -s tests -v`

Getestet werden unter anderem Risikolimits, Zeichenkodierung, zeitlich getrennte Daten, Quellenprüfung, ausschließlich lokale Sprachmodellanfragen, Strategieparameter, konservative Stopbehandlung, Kosten, Modellvergleich und Wiederverwendungssperre für Testzeiträume. Die Tests verwenden simulierte Modell-/Netzwerkantworten. Ollama auf deiner GPU, reale RSS-Abrufe und MT5-Orders müssen noch auf Windows geprüft werden. Der Entwicklungs-Sandbox fehlen die nötige Windows-/MT5-Laufzeit und ein lokales Ollama-Modell.
