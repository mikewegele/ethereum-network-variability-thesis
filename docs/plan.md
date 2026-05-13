# Finaler Plan für die Masterarbeit

## 1. Ziel der Arbeit

Die Arbeit untersucht, wie sich Network Variability auf **Performance**, **Liveness** und vor allem **Consensus Stability** in **QBFT-basierten privaten Ethereum-Netzwerken mit Hyperledger Besu** auswirkt.

Im Zentrum steht nicht nur die Frage, ob das System noch Blöcke finalisiert, sondern **wie stabil und geordnet** diese Finalisierung unter verschlechterten Netzwerkbedingungen noch abläuft.

Die Arbeit analysiert damit den Übergang zwischen drei operativen Regimen:
- **stable**
- **degraded**
- **stalled**

und identifiziert die jeweiligen **robustness boundaries**.

---

## 2. Finales experimentelles Setup

### Netzwerk
- 4 QBFT-Validatoren
- 1 zusätzlicher RPC-/Client-Zugangspunkt
- Docker Compose
- Hyperledger Besu
- feste Validator-Membership
- fixe Topologie über die gesamte Hauptserie

### Konsenskonfiguration
- `blockperiodseconds = 2`
- `requesttimeoutseconds = 4`
- `epochlength = 30000`
- `chainId = 1337`

### Workload
- Transaktionstyp: **einfache Ether-Transfers**
- Submission-Modus: **open-loop**
- Zielrate: **5 tx/s** für Hauptserie
- Pilot-/Smoke-Tests auch mit 1 tx/s und 10 tx/s möglich
- Ziel: Konsensschicht beobachten, nicht Smart-Contract-Ausführung benchmarken

### Wiederholungen
- **5 Runs pro Szenario** in der finalen Hauptserie
- Vorher Pilot- und Smoke-Tests mit 1–3 Runs

---

## 3. Finaler Run-Aufbau

### Für die Hauptserie: phased runs
Jeder Run soll dieselbe klare Struktur haben:

- **warm-up = 60 s**
- **pre-impairment / baseline = 60 s**
- **impairment = 180 s**
- **recovery = 60 s**
- **total duration = 360 s**

### Begründung
Damit lassen sich innerhalb eines einzelnen Runs sauber unterscheiden:
- nominales Verhalten
- Verhalten unter aktivem Impairment
- Erholung nach Entfernen des Impairments

Für **persistente Szenarien** kann alternativ auch ein steady run genutzt werden, aber für die Thesis-Hauptserie ist das phased design methodisch stärker.

---

## 4. Finale Szenariomatrix

## 4.1 Baseline
Ohne künstliches Impairment.

Ziel:
- Referenzwerte für Inter-Block-Zeiten
- Referenzwerte für Throughput
- Referenzwerte für Delayed Finalization
- Referenzverteilung für Thresholds und Regime-Zuordnung

### Baseline-Plan
- 5 Repetitions
- gleiche Run-Struktur wie Hauptserie
- kein Impairment in der Stress-Phase

---

## 4.2 Latency-Szenarien
Symmetrische zusätzliche Verzögerung auf validator-to-validator traffic.

### Levels
- 0 ms
- 50 ms
- 100 ms
- 200 ms
- 400 ms
- 800 ms

### Ziel
Untersuchen, ab wann reine Verzögerung zu:
- deutlich längerer Finalisierung
- unregelmäßigen Blockintervallen
- vermehrten Round Changes
- partieller oder vollständiger Stallbildung führt

---

## 4.3 Packet-Loss-Szenarien
Symmetrischer zufälliger Paketverlust auf validator-to-validator traffic.

### Levels
- 0 %
- 1 %
- 3 %
- 5 %
- 10 %
- 20 %

### Ziel
Untersuchen, wie unvollständige Nachrichtenübermittlung die Konsensphasen destabilisiert.

**Hinweis:** Diese Szenarien werden erst aktiviert, sobald das Loss-Script sauber implementiert ist.

---

## 4.4 Bandwidth-Szenarien
Begrenzung des validator-to-validator Durchsatzes.

### Levels
- unlimited
- 10 mbit
- 1 mbit
- 128 kbit
- 64 kbit

### Ziel
Untersuchen, wann reduzierte Kapazität nicht nur Throughput senkt, sondern konsensrelevante Kommunikation selbst destabilisiert.

---

## 4.5 Partition-/Offline-Szenarien
Da in deinem Setup derzeit `apply_offline.sh` verwendet wird, werden zunächst **validator drop / disconnection scenarios** operationalisiert.

### Levels
- 1 Validator offline
- 2 Validatoren offline

### Analytische Bedeutung
- **1 offline**: 3 von 4 Validatoren bleiben verfügbar → Quorum prinzipiell noch möglich
- **2 offline**: 2 von 4 Validatoren bleiben verfügbar → Quorum nicht mehr möglich

### Ziel
Die Grenze zwischen noch möglicher und strukturell unmöglicher QBFT-Finalisierung sichtbar machen.

### Spätere Erweiterung
Wenn du echte gerichtete Partitionen implementierst, dann zusätzlich:
- 3|1 Partition
- 2|2 Partition

---

## 4.6 Kombinierte Szenarien
Nur nachdem Single-Factor-Szenarien stabil laufen.

### Initiale Levels
- 250 ms + 1 mbit
- 500 ms + 1 mbit
- 250 ms + 5 % loss
- 500 ms + 5 % loss

### Ziel
Untersuchen, ob Kombinationsstörungen früher oder abrupter in degraded/stalled regimes führen.

---

## 5. Finales Messziel pro Run

Pro Run sollen mindestens folgende Daten vorliegen:

### Blockchain-/RPC-Daten
- Blocknummern
- Blocktimestamps
- txCount pro Block
- peerCount
- Validator-Set per block / latest

### Besu-/Protokollsignale
- importierte / produzierte Blöcke
- Round Changes
- Timeout-bezogene Ereignisse
- Hinweise auf Stall / fehlende Finalisierung

### Workload-Daten
- gesendete Transaktionen
- failed submissions
- effektive Send-Rate
- Backlog / pending nonce behavior

### NetEm-/Fault-Injection-Daten
- aktives Impairment
- Aktivierungszeitpunkt
- Deaktivierungszeitpunkt
- Parameter des Impairments

---

## 6. Finale Auswertung für die Thesis

## 6.1 Primäre Kennzahlen

### Performance
- inter-block time
- chain growth rate
- tx_total
- tx_per_block

### Liveness
- stall_event_count
- stall_duration
- missing finalization intervals
- recovery after impairment removal

### Consensus Stability
- delayed finalization
- irregular inter-block timing
- increased round changes
- temporäre Unterbrechungen trotz späterer Recovery

---

## 6.2 Regime-Zuordnung

### Stable
- Blockproduktion bleibt regelmäßig
- keine oder fast keine Missing-Finalization-Intervalle
- keine prolongierten Stalls
- Verhalten bleibt nahe Baseline

### Degraded
- Blöcke werden noch finalisiert
- aber mit erkennbar höherer Unregelmäßigkeit
- oder deutlich längeren Inter-Block-Zeiten
- oder Round-Change-/Timeout-Symptomen
- oder temporären Finalisierungslücken

### Stalled
- über einen zusammenhängenden relevanten Zeitraum keine Finalisierung mehr
- während aktiver Last
- Quorum operativ nicht mehr erreichbar bzw. Konsensfortschritt nicht mehr beobachtbar

---

## 6.3 Robuste Schwellenlogik

Für die Thesis sollten die Regime **nicht rein impressionistisch**, sondern regelbasiert zugeordnet werden.

### Geplante Regelbasis
- **Delayed finalization**: oberhalb des 95. Perzentils der Baseline
- **Missing finalization interval**: kein finalisierter Block in `2 × blockperiodseconds`
- **Stall**: längeres zusammenhängendes Ausbleiben finalisierter Blöcke unter aktiver Last
- **Robustness boundary**: reproduzierbarer Übergang von stable → degraded oder degraded → stalled bei steigender Impairment-Severity

Für die finale Thesis-Schreibversion sollten diese Regeln noch explizit in decision logic formuliert werden.

---

## 7. Was bereits erfolgreich gezeigt wurde

Der aktuelle Stand zeigt bereits:
- QBFT-Netzwerk startet stabil
- Validatoren peeren korrekt
- leere Blöcke werden regelmäßig produziert
- echte Ether-Transfer-Transaktionen werden akzeptiert
- Blöcke mit Transaktionen werden produziert
- Baseline-Runs mit `run_matrix.sh` funktionieren
- Collector, Load Generator und Analysepfad laufen zusammen

Das bedeutet:
**Die Pilotstudie ist erfolgreich bestanden.**

---

## 8. Was jetzt noch implementiert werden soll

## 8.1 Sofort
1. **plan.md festhalten**
2. **Baseline finalisieren**
3. **Latency-Runs finalisieren**
4. **Bandwidth-Runs finalisieren**
5. **Offline-/Disconnection-Runs finalisieren**

## 8.2 Danach
6. `apply_loss.sh` implementieren
7. Packet-Loss-Szenarien durchführen
8. Optional kombinierte Szenarien

## 8.3 Danach
9. Analyse-Skripte prüfen und ggf. erweitern
10. Resultate tabellarisch zusammenführen
11. Methodology-Kapitel auf finale Werte umschreiben
12. Results-Kapitel aus den Run-Ergebnissen aufbauen

---

## 9. Finaler Arbeitsplan in der richtigen Reihenfolge

## Phase A — Implementierung abschließen
Ziel: alles lauffähig machen, bevor du die Hauptserie startest.

1. Baseline-Modus stabil
2. Latency-Skripte stabil
3. Bandwidth-Skripte stabil
4. Offline-Skripte stabil
5. Loss-Skript ergänzen
6. Analysepfad auf alle Modi testen

## Phase B — Pilot-Runs je Modus
Ziel: prüfen, ob Daten sauber sind.

- 1 kurzer Baseline-Run
- 1 kurzer Latency-Run
- 1 kurzer Bandwidth-Run
- 1 kurzer Offline-Run
- später 1 kurzer Loss-Run

## Phase C — Hauptserie durchführen
Ziel: Daten für die Thesis sammeln.

Geplant:
- 5 Repetitions pro Szenario
- phased runs
- feste Konfiguration
- fester Workload
- vollständige Datensammlung

## Phase D — Auswertung
Ziel: Ergebnisse thesis-fähig machen.

- baseline zusammenfassen
- impairment categories einzeln vergleichen
- severity levels vergleichen
- stable/degraded/stalled markieren
- robustness boundaries identifizieren

## Phase E — Schreiben
Ziel: Methodology und Results finalisieren.

- Methodology auf echte Werte umstellen
- Tabellen mit Szenariomatrix einfügen
- Operationalisierung mit finalen Schwellen präzisieren
- Results entlang der Regime-Logik strukturieren

---

## 10. Konkrete finale Parameter für die Thesis-Version

Diese Werte sind der aktuelle Zielstand für die Hauptserie:

### QBFT
- `blockperiodseconds = 2`
- `requesttimeoutseconds = 4`

### Workload
- transaction type = simple Ether transfer
- submission mode = open-loop
- target rate = 5 tx/s

### Run structure
- warm-up = 60 s
- pre-impairment = 60 s
- impairment = 180 s
- recovery = 60 s
- total duration = 360 s

### Scenarios
- latency levels = 0, 50, 100, 200, 400, 800 ms
- packet-loss levels = 0, 1, 3, 5, 10, 20 %
- bandwidth levels = unlimited, 10 mbit, 1 mbit, 128 kbit, 64 kbit
- partition/offline scenarios = 1 validator offline, 2 validators offline

### Repetitions
- runs per scenario = 5

---

## 11. Wichtig für die Thesis-Schreiblogik

Das hier sind **nicht nur technische Testläufe**.

Die Baseline-Runs und die späteren Impairment-Runs bilden direkt die empirische Grundlage für:
- die Baseline-Referenz
- die Schwellenbildung
- die Regime-Zuordnung
- die Identifikation der Robustness Boundaries
- das spätere Results-Kapitel

Die aktuellen kurzen Runs sind noch **Pilot- und Validierungsruns**.
Die eigentliche Hauptserie beginnt erst, wenn alle relevanten Modi stabil implementiert und getestet sind.

---

## 12. Nächster konkreter Schritt

Der nächste sachlich richtige Schritt ist:

1. **Implementierung der noch fehlenden Net-Skripte abschließen**
2. **phased execution sauber in run_matrix verwenden**
3. **einen vollständigen sauberen Pilotlauf pro Modus durchführen**
4. **danach Hauptserie starten**

Erst **danach** sollte das Methodology-Kapitel final auf diese festen Werte umgeschrieben werden.