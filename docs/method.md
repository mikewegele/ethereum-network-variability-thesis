# Herleitung der Stichprobengröße für die Experimente

## Ziel

Die Anzahl der Wiederholungen pro Szenariofamilie wurde nicht frei gewählt, sondern über eine **pilotdatenbasierte Präzisionsanalyse** bestimmt. Ziel war es, eine methodisch begründete Replikationszahl zu erhalten, statt eine Zahl nur pragmatisch festzulegen.

Als Datenbasis wurde die bereits erzeugte Datei

`experiments/exports/final_series/summary.csv`

verwendet.

Es wurden nur erfolgreiche Runs (`status = ok`) berücksichtigt.

---

## Grundidee der Methode

Die Stichprobengröße wurde über eine **präzisionsbasierte Stichprobenplanung** bestimmt. Dabei wird gefragt:

> Wie viele Wiederholungen sind nötig, damit der Mittelwert einer ausgewählten Zielmetrik mit einer vorab festgelegten Genauigkeit geschätzt werden kann?

Verwendet wurde die Formel für ein 95%-Konfidenzintervall:

\[
n = \left(\frac{1.96 \cdot \sigma}{E}\right)^2
\]

Dabei gilt:

- \(n\): erforderliche Stichprobengröße
- \(\sigma\): empirisch geschätzte Standardabweichung aus den Pilotruns
- \(E\): maximal akzeptierter Schätzfehler
- \(1.96\): z-Wert für ein 95%-Konfidenzintervall

Der berechnete Wert wurde anschließend auf die nächste ganze Zahl **aufgerundet**.

---

## Warum diese Methode?

Diese Methode passt gut zum vorliegenden Experiment, weil hier nicht ein einzelner formaler Hypothesentest im Vordergrund steht, sondern die Frage, mit wie vielen Wiederholungen sich das Verhalten des Systems **hinreichend präzise** beschreiben lässt.

Die Stichprobengröße wurde also nicht über einen Signifikanztest, sondern über die gewünschte **Schätzgenauigkeit** bestimmt.

---

## Verwendete Planungsmetriken

Die Stichprobengröße wurde **getrennt pro Szenariofamilie** bestimmt.

### Für Latency, Packet Loss und Bandwidth
Als primäre Planungsmetrik wurde verwendet:

`stress_phase_block_time_mean_s`

Diese Metrik beschreibt die mittlere Inter-Block-Zeit in der Stress-Phase und ist für die Forschungsfrage gut geeignet, weil sie direkt abbildet, wie stark sich die Regelmäßigkeit des Konsensfortschritts unter aktivem Impairment verändert.

### Für Offline
Für die Offline-Szenarien wurde stattdessen verwendet:

`stress_phase_stall_duration_total_s`

Der Grund ist, dass bei Offline-Szenarien Inter-Block-Zeiten in stärkeren Ausfallfällen weniger aussagekräftig sein können, während Stall-Dauer direkt den Verlust von Fortschritt abbildet.

---

## Wie die Referenzfälle gewählt wurden

Die Referenzfälle wurden **nicht** einfach nach maximaler Streuung gewählt und auch **nicht** nach Gefühl. Stattdessen wurde pro Szenariofamilie ein **zahlenbasiert definierter erster klar degradierter Fall** ausgewählt.

### Regel für Latency, Packet Loss und Bandwidth

Ausgangspunkt ist das Baseline-Niveau der Stress-Phase-Blockzeit von ungefähr **2.0 Sekunden**.

Ein Fall wurde dann als **klar degradiert** gewertet, wenn seine mittlere Stress-Phase-Blockzeit mindestens **50 % über dem Baseline-Niveau** lag.

Das numerische Kriterium lautete also:

\[
\text{stress\_phase\_block\_time\_mean\_s} \ge 3.0
\]

weil

\[
2.0 \cdot 1.5 = 3.0
\]

Anschließend wurde jeweils der **erste** Level gewählt, der diese Bedingung erfüllt. Auf diese Weise wurden keine Baseline-nahen und auch keine extremen Kollapsfälle als Referenz verwendet, sondern der erste numerisch klar degradierte Zustand.

### Konkrete Auswahl

#### Latency
Auszug aus den Mittelwerten:

- 2500 ms: 2.924638
- 3000 ms: 3.260459
- 3500 ms: 4.057817

Der erste Level mit Mittelwert \(\ge 3.0\) war:

**Latency = 3000 ms**

#### Packet Loss
Auszug aus den Mittelwerten:

- 50 %: 2.445452
- 55 %: 3.494669
- 60 %: 6.462238

Der erste Level mit Mittelwert \(\ge 3.0\) war:

**Packet Loss = 55 %**

#### Bandwidth
Auszug aus den Mittelwerten:

- 32kbit: 2.628674
- 24kbit: 3.294154
- 16kbit: 3.781234

Der erste Level mit Mittelwert \(\ge 3.0\) war:

**Bandwidth = 24kbit**

#### Offline
Für Offline wurde diese 50%-Regel nicht verwendet, da der Fall `offline = 2` einen strukturellen Quorumverlust darstellt und damit kein normal degradierter, sondern ein struktureller Ausfallfall ist.

Daher wurde als Referenz genommen:

**Offline = 1**

---

## Festlegung des Präzisionsziels

Für die Metrik `stress_phase_block_time_mean_s` wurde festgelegt:

\[
E = 0.5 \text{ s}
\]

Das bedeutet:

Der Mittelwert der Stress-Phase-Inter-Block-Zeit soll mit einer Genauigkeit von ungefähr **±0.5 Sekunden** geschätzt werden.

Dieser Wert wurde relativ zur nominalen Blockperiode von **2 Sekunden** festgelegt. Damit entspricht der tolerierte Schätzfehler **25 % der konfigurierten Blockperiode**. Diese Präzision ist ausreichend streng, um relevante Degradation gegenüber dem Normalverhalten sichtbar zu machen, ohne die erforderliche Stichprobengröße unrealistisch stark anwachsen zu lassen.

Für die Metrik `stress_phase_stall_duration_total_s` wurde festgelegt:

\[
E = 30.0 \text{ s}
\]

Das bedeutet:

Die mittlere Stall-Dauer soll mit einer Genauigkeit von ungefähr **±30 Sekunden** geschätzt werden.

---

## Berechnung pro Szenariofamilie

### 1. Latency

- Referenzfall: `3000 ms`
- Metrik: `stress_phase_block_time_mean_s`
- Anzahl vorhandener Pilotruns: `15`
- Geschätzte Standardabweichung:

\[
\sigma = 1.169512
\]

- Präzisionsziel:

\[
E = 0.5
\]

Eingesetzt in die Formel:

\[
n = \left(\frac{1.96 \cdot 1.169512}{0.5}\right)^2
\]

\[
n \approx 21.01
\]

Aufgerundet:

\[
n = 22
\]

**Ergebnis für Latency: 22 Repetitionen**

---

### 2. Packet Loss

- Referenzfall: `55 %`
- Metrik: `stress_phase_block_time_mean_s`
- Anzahl vorhandener Pilotruns: `5`
- Geschätzte Standardabweichung:

\[
\sigma = 0.717532
\]

- Präzisionsziel:

\[
E = 0.5
\]

Eingesetzt:

\[
n = \left(\frac{1.96 \cdot 0.717532}{0.5}\right)^2
\]

\[
n \approx 7.91
\]

Aufgerundet:

\[
n = 8
\]

**Ergebnis für Packet Loss: 8 Repetitionen**

---

### 3. Bandwidth

- Referenzfall: `24kbit`
- Metrik: `stress_phase_block_time_mean_s`
- Anzahl vorhandener Pilotruns: `5`
- Geschätzte Standardabweichung:

\[
\sigma = 0.436872
\]

- Präzisionsziel:

\[
E = 0.5
\]

Eingesetzt:

\[
n = \left(\frac{1.96 \cdot 0.436872}{0.5}\right)^2
\]

\[
n \approx 2.93
\]

Aufgerundet:

\[
n = 3
\]

**Ergebnis für Bandwidth: 3 Repetitionen**

---

### 4. Offline

- Referenzfall: `1`
- Metrik: `stress_phase_stall_duration_total_s`
- Anzahl vorhandener Pilotruns: `6`
- Geschätzte Standardabweichung:

\[
\sigma = 26.944387
\]

- Präzisionsziel:

\[
E = 30.0
\]

Eingesetzt:

\[
n = \left(\frac{1.96 \cdot 26.944387}{30.0}\right)^2
\]

\[
n \approx 3.10
\]

Aufgerundet:

\[
n = 4
\]

**Ergebnis für Offline: 4 Repetitionen**

---

## Endergebnis

Die berechneten Stichprobengrößen pro Szenariofamilie lauten damit:

- **Latency:** 22
- **Packet Loss:** 8
- **Bandwidth:** 3
- **Offline:** 4

---

## Interpretation

Die Ergebnisse zeigen, dass die erforderliche Anzahl an Wiederholungen **zwischen den Szenariofamilien deutlich variiert**.

Der Grund dafür ist, dass die empirische Streuung der jeweiligen Zielmetriken unterschiedlich groß ist:

- Höhere Streuung führt zu größerem erforderlichem \(n\)
- Geringere Streuung führt zu kleinerem erforderlichem \(n\)

Damit wurde die Replikationszahl **datenbasiert** und **familienbezogen** bestimmt.

---

## Konsequenz für eine einheitliche Replikationszahl

Falls eine **einheitliche Replikationszahl über alle Szenariofamilien hinweg** verwendet werden soll, muss das Maximum der berechneten Werte genommen werden.

Das Maximum ist:

\[
n = 22
\]

Damit wäre **22** die konservative gemeinsame Replikationszahl über alle betrachteten Szenariofamilien hinweg.

---

## Zusammenfassung

Die Stichprobengröße wurde über eine pilotdatenbasierte Präzisionsanalyse bestimmt. Dafür wurde pro Szenariofamilie ein zahlenbasiert definierter erster klar degradierter Referenzfall ausgewählt. Aus den vorhandenen Pilotruns dieses Referenzfalls wurde die Standardabweichung der jeweiligen primären Zielmetrik geschätzt. Anschließend wurde mit einem vorab festgelegten Präzisionsziel die erforderliche Anzahl an Wiederholungen berechnet.

Die berechneten Werte lauten:

- Latency = 22
- Packet Loss = 8
- Bandwidth = 3
- Offline = 4

Falls eine gemeinsame Replikationszahl für alle Szenariofamilien verwendet werden soll, ergibt sich daraus:

- **einheitliche Replikationszahl = 22**