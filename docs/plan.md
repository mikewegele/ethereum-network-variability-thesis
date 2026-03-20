Hier ist ein vollständiger Entwurf für dein Versuchsdesign, den du direkt als Grundlage für Kapitel 5 (Design) und Kapitel 6 (Implementation) deiner Masterarbeit verwenden kannst. Ich habe die Parameter so gewählt, dass sie wissenschaftlich belastbar sind und genau zu den theoretischen Grundlagen deines PDFs (IBFT, $3f+1$, Quoren) passen.
------------------------------
Versuchsdesign: Impact of Network Variability on IBFT Stability1. Forschungsziel
Das Ziel der Experimente ist die Bestimmung der Stabilitätsgrenzen (Stability Boundaries) von IBFT. Es soll quantifiziert werden, ab welchen Schwellenwerten für Latenz, Paketverlust und Bandbreite die Konsensbildung verzögert wird, wann Round-Changes (Liveness-Einbußen) auftreten und unter welchen Bedingungen die Blockproduktion vollständig zum Erliegen kommt.
------------------------------
2. System-Konfiguration (Testbed)2.1 Software-Stack

* Blockchain-Client: Hyperledger Besu (v24.x oder aktuellste stabile Version).
* Konsens-Algorithmus: IBFT 2.0 (Istanbul Byzantine Fault Tolerance).
* Virtualisierung: Docker & Docker Compose zur Isolation der Validatoren.
* Netzwerk-Emulation: Pumba (für Chaos Engineering in Docker) oder Linux TC (Traffic Control) mit NetEm.
* Workload-Generator: Hyperledger Caliper (für konstante Transaktionslast).

2.2 Netzwerk-Topologie
Um die Resilienz-Grenzwerte $n \geq 3f+1$ zu prüfen, werden zwei Setups gefahren:

1. Kleines Setup (n=4): $f=1$ (Ein Byzantinischer Fehler erlaubt), Quorum-Größe: 3.
2. Skalierungs-Setup (n=7): $f=2$ (Zwei Byzantinische Fehler erlaubt), Quorum-Größe: 5.

------------------------------
3. Experimentelle Matrix (Szenarien)
   Jedes Experiment läuft über 10 Minuten mit einer konstanten Last von 50 Transaktionen pro Sekunde (TPS), um eine Sättigung des Netzwerks durch den Konsens-Overhead (nicht durch die EVM) zu provozieren.

| ID     | Parameter | Wertebereich (Schritte) | Zielsetzung |
|--------|---|---|---|
| EXP-01 | Latenz (RTT) | 0ms $\rightarrow$ 2000ms (+200ms) | Identifikation des Kipppunkts für den requestTimeout. |
| EXP-02 | Bandbreite | 100 Mbps $\rightarrow$ 128 Kbps (logarithmisch) | Test der $O(n^2)$ Nachrichten-Komplexität bei Engpässen. |
| EXP-03 | Partition | Isolation von $f$ vs. $f+1$ Knoten | Verifikation der Liveness-Unterbrechung bei Quorum-Unterschreitung. |

------------------------------
4. Messgrößen (KPIs)
   Die Daten werden sekündlich aus den Besu-Metriken (via Prometheus/Grafana) und den Logs extrahiert:

    1. Block Finalization Latency: Durchschnittliche Zeit (ms) vom Erstellen des Block-Proposals bis zum Commit.
    2. Round-Change Count: Anzahl der initiierten Rundenwechsel pro Blockhöhe (Indikator für Instabilität).
    3. Throughput (TPS): Tatsächlich finalisierte Transaktionen pro Sekunde.
    4. Message Overhead: Anzahl der IBFT-Kontrollnachrichten (Pre-Prepare, Prepare, Commit) im Verhältnis zur Last.

------------------------------
5. Versuchsablauf (Protokoll)
   Für jedes Szenario wird folgender automatisierter Prozess angewendet:

    1. Phase 1: Warm-up (60s): Start des Netzwerks, Erreichen einer stabilen Blockhöhe ohne Störungen.
    2. Phase 2: Baseline (120s): Messung der Performance unter idealen Bedingungen.
    3. Phase 3: Stress-Injektion (300s): Applikation des Netzwerk-Fehlers (z.B. Erhöhung der Latenz auf allen Validator-Links).
    4. Phase 4: Recovery (120s): Entfernen der Störung und Beobachtung der "Catch-up"-Zeit (Synchronisation der verpassten Blöcke).
    5. Phase 5: Teardown: Löschen der Ledger-Daten für den nächsten sauberen Durchlauf.

------------------------------
6. Analyse-Strategie (Kapitel 7 Vorbereitung)

* Korrelation: Vergleich von Round-Change-Events mit der injizierten Latenz.
* Schwellenwert-Analyse: Bestimmung der "Critical Latency" $L_{crit}$, ab der die Blockzeit exponentiell ansteigt.
* Quorum-Stabilität: Analyse, ob das Netzwerk bei $k = 2f+1$ erreichbaren Knoten (deine Formel aus 2.7.5) stabil bleibt oder bereits durch Jitter instabil wird.
