# AURUM Demo Terminal

Experimenteller lokaler Windows-Prototyp für automatischen XAUUSD-Demohandel mit MetaTrader 5. Enthält ein Browser-Dashboard, Einstiegssperren, SQLite-Journal und ein lernendes logistisches Modell. Keine Quantenberechnung, kein fertiges oder als profitabel validiertes Produkt.

## Auf Windows starten

1. Python **3.12, 64-bit** von python.org installieren, inklusive Python Launcher.
2. MT5 öffnen und auf dem **Demokonto** anmelden. In der Marktübersicht XAUUSD einblenden. Falls der Broker GOLD oder einen Symbolzusatz verwendet, `symbol` in `config.json` anpassen.
3. Einen M5-Chart öffnen und historische Daten laden lassen. Mindestens 800 abgeschlossene Kerzen pro verwendeter Zeitebene sind nötig; das Programm fragt bis zu 4.000 ab.
4. In MT5 unter Extras → Optionen → Expert Advisors den algorithmischen Handel zulassen und die Option, die automatischen Handel über die externe Python-API deaktiviert, ausschalten. Algo Trading aktivieren.
5. `start.bat` doppelklicken. Es erstellt eine virtuelle Python-Umgebung und installiert Pakete. Browseradresse: http://127.0.0.1:8765. Das Konsolenfenster offen lassen.
6. Status prüfen und **Demohandel starten** anklicken. Jeder Start der Anwendung beginnt pausiert. Ohne genehmigtes Modell oder bei Filtern werden keine Orders eröffnet. Das kann über längere Zeit so bleiben.

Zugangsdaten bleiben ausschließlich in MT5. Das Programm akzeptiert nur Konten, die MT5 ausdrücklich als Demo meldet; MetaQuotes-Demo ist keine Voraussetzung. Manche Demoserver bieten Gold nicht an. Dann ist ein Demokonto eines Brokers mit XAUUSD erforderlich. Konto-ID und Server werden lokal gespeichert, um Journale verschiedener Konten nicht zu vermischen. Für ein anderes Konto einen frischen Programmordner nutzen.

## Regeln und No-Trading-Zonen

`config.json` bei pausierter Anwendung bearbeiten; sie wird alle fünf Sekunden neu gelesen:

- `risk_percent`: geplantes Risiko pro Einstieg in Prozent der Equity (Standard 0,25). Mindestlot wird nicht aufgerundet. Spread, Ausführung und Kurslücken können reale Verluste erhöhen.
- `daily_loss_percent`: blockiert neue Einstiege ab 2 % Equity-Verlust gegen die erste gespeicherte Equity des UTC-Tages. Kontoweite Grenze einschließlich manueller Trades, Ein-/Auszahlungen und offener Verluste. **Keine automatische Liquidation**, kein garantiertes Verlustmaximum.
- `price_zones`: z. B. `[[2700, 2715], [2750, 2760]]`. Absolute Preisbereiche, keine automatisch erkannten Chartzonen.
- `blocked_hours_utc`: gesperrte volle Stunden in UTC; Sommer-/Winterzeit beachten.
- `blocked_windows_utc`: z. B. `[["2026-11-06T13:15:00+00:00", "2026-11-06T14:15:00+00:00"]]`. Manuelle Ereignissperren. **Kein Nachrichtenfeed**.
- `max_spread_atr`: Spread relativ zur M5-ATR; Standard 0,12.
- `min_probability`: Signalgrenze 0,65. Modellwerte sind unkalibrierte Schätzungen, keine verlässlichen Gewinnwahrscheinlichkeiten.

Es gibt höchstens eine offene Position im Symbol (auch manuelle Positionen sperren Einstiege). Pro geschlossener Kerze der Ausführungszeitebene erfolgt höchstens ein Orderversuch. Stop-Loss und Take-Profit werden mit der Order an MT5 gesendet. Ein abgelehnter Versuch wird in derselben Kerze nicht wiederholt. Bei Fehlern pausiert der Bot; MT5 prüfen und bei Bedarf neu starten. Nur eine Programminstanz pro MT5-Terminal betreiben.

**Einstiege stoppen** schließt keine Positionen. Beendest du den Dienst, bleiben bereits beim Broker liegende SL/TP bestehen. Schutzorders garantieren keinen Ausführungspreis. Positionen direkt in MT5 kontrollieren.

## Was hier „Lernen“ bedeutet

Jede konfigurierte Zeitebene erhält ein eigenes Modell. Jedes Modell lernt aus Kursmerkmalen (Momentum und Schwankung) die Richtung drei Kerzen seiner eigenen Zeitebene später. Der letzte Teil der Historie bleibt als chronologischer Test getrennt; drei Trainingskerzen vor dem Test werden ausgelassen. Unter 55 % Balanced Accuracy sind Einstiege gesperrt. Das ist eine einfache Forschungsschranke, **kein kostenbereinigter Backtest und keine hinreichende Freigabe für Echtgeld**.

Jede vom Bot eröffnete und vollständig geschlossene Position wird mit Nettogewinn inklusive verfügbarer Gebühren und getrennten Merkmalen jeder verfügbaren Zeitebene gespeichert. Bei späteren stündlichen Trainingsläufen ergänzen ausreichend alte Ergebnisse das Training; der Testzeitraum bleibt ausgeschlossen. Gebührenfreier Nullgewinn wird nicht als Lernergebnis verwendet. Es erfolgt keine unkontrollierte Modelländerung nach jedem einzelnen Trade. Fehlgeschlagene Kandidaten sperren neue Einstiege, statt ein altes Modell weiterlaufen zu lassen.

Grenzen: Rückblicktest ohne echte Handelsausführung; Klassifikationsziel und tatsächlicher SL/TP-Ausgang unterscheiden sich. Historische Muster und laufende Trades sind abhängig. Modellwerte sind unkalibriert. Keine automatische Strategieoptimierung, kein Vergleich gegen ein produktives Champion-Modell, kein vollständiges Walk-forward-Verfahren, keine Newsdaten, kein Echtgeldmodus. Positionsmanagement über SL/TP, keine Trailing-Stops oder zeitgesteuerten Ausstiege. Das System enthält noch keinen belastbaren Profitabilitätsnachweis.

## Prüfung und Daten

`python -m unittest discover -s tests -v` prüft Risikoregeln, Zonen und grundlegende Modellfunktionen. Der HTTP-Laufzeittest wurde durch das Socket-Verbot der Entwicklungs-Sandbox blockiert. Die tatsächliche Windows-/MT5-Verbindung und Broker-Orders müssen auf deinem Demokonto geprüft werden; sie konnten in der Linux-Entwicklungsumgebung nicht getestet werden.

Lokale Dateien: `trades.sqlite` (Journal/Trainingsdaten/Tagesbasis), `account.json` (Kontobindung). Nicht löschen, während die Anwendung läuft. Das Dashboard lauscht nur auf 127.0.0.1 und nutzt ein Sitzungstoken für Start/Stopp. Kein Netzwerkzugriff oder Cloudhosting eingerichtet.


## Mehrere Zeitebenen (Version 2)

Standardmäßig werden **M1, M5, M15, M30, H1, H4 und D1** separat trainiert. MT5 muss dafür keine sieben Charts geöffnet haben: Die Daten werden direkt über die API geladen. Jeder historische Test und jedes stündliche Training gehören nur zu ihrer jeweiligen Zeitebene. Trade-Ergebnisse ergänzen jedes Modell mit dessen eigenen Merkmalen vom Zeitpunkt des Einstiegs. Diese Modelle lernen allerdings alle aus denselben ausgeführten Trades; Bestätigungen sind keine statistisch unabhängigen Belege.

In `config.json` steuert `timeframes` die Trainingszeitebenen, `execution_timeframe` die Einstiegstaktung und ATR-Risikoberechnung (Standard M5). Alle nativen MT5-Zeitebenen sind als Namen konfigurierbar: M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12, D1, W1, MN1. Broker müssen mindestens 800 geschlossene Kerzen pro Zeitebene bereitstellen. Besonders W1/MN1 haben häufig zu wenig Historie. Fehlende Daten werden im Dashboard angezeigt und liefern keine Bestätigung.

Das Ausführungsmodell muss den Test bestehen und ein ausreichend starkes Signal liefern. Mindestens `min_confirmations` (Standard 2, einschließlich Ausführungsmodell) geprüfte Modelle müssen die gleiche Richtung mit der eingestellten Signalstärke bestätigen. Gibt ein anderes geprüftes Modell ein ausreichend starkes Gegensignal, werden Einstiege gesperrt. Ungeprüfte oder unsichere Modelle enthalten sich. Bei fehlenden Daten der Ausführungszeitebene pausiert der Dienst. Fehlende optionale Zeitebenen verhindern Handel nicht, sofern genug andere Modelle bestätigen.

Der Dashboard-Kurschart zeigt die Ausführungszeitebene; die Modellübersicht zeigt Status und Prognose aller konfigurierten Zeitebenen. Das Umschalten eines Charts in MT5 ändert die Konfiguration des Bots nicht. Änderungen an `timeframes` oder `execution_timeframe` bitte pausiert vornehmen und die Anwendung danach neu starten.

Bestehende Journale werden unterstützt: Ältere Trades enthalten nur M5-Merkmale und ergänzen ausschließlich das M5-Modell. Neue Trades speichern getrennte Merkmalsvektoren je verfügbarer Zeitebene. Es werden weiterhin ausschließlich das konfigurierte Goldsymbol und ein Demokonto gehandelt, keine weiteren Instrumente automatisch hinzugefügt.


## Update bei falsch dargestellten Umlauten (Windows)

Die Version mit expliziter UTF-8-Kodierung behebt falsche Umlaute, Trennzeichen und Pfeile im gesamten Dashboard. Ursache war das Einlesen der UTF-8-HTML-Datei mit der Windows-Standardkodierung. Auch JSON-Antworten und die Windows-Konsole verwenden nun ausdrücklich UTF-8.

1. Im Dashboard neue Einstiege stoppen. Das Konsolenfenster anschließend schließen. Offene Positionen weiterhin in MT5 kontrollieren.
2. Die aktuelle ZIP von GitHub herunterladen und in einen separaten Ordner entpacken.
3. Aus dem neuen Ordner nur `app.py` und `start.bat` in den bisherigen Programmordner kopieren und ersetzen. `config.json`, `account.json` und `trades.sqlite` behalten, damit Einstellungen und Journal erhalten bleiben.
4. `start.bat` im bisherigen Ordner starten, dann im Browser **Strg+F5** drücken. Falls die Seite zu früh geöffnet wurde, nach dem Start nochmals neu laden.

Die Korrektur verändert keine Handelsfilter oder Modellschwellen. Eine Meldung über nicht bestandene Modellvalidierung ist weiterhin eine eigenständige Einstiegssperre.
