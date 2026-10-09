# RELEASE NOTES v5.62 — właściwa grupa 1–3, fallback ogólni, WF na końcu

## Najważniejsza zmiana
Dyżury na korytarzu 1–3 mają teraz hierarchię:
1. nauczyciele grupy 1–3,
2. nauczyciele ogólni („school”) jako fallback,
3. nauczyciele WF dopiero jako ostatni fallback.

Nie jest to zwykły koszt wagowy. Po znalezieniu pełnej obsady CP-SAT wykonuje osobne etapy leksykograficzne:
- minimalizuje łączną liczbę przydziałów spoza właściwej grupy,
- przy tej samej minimalnej liczbie obcych przydziałów minimalizuje liczbę WF na 1–3,
- dopiero potem optymalizuje fairness i pozostałe soft constraints.

## Dlaczego
Poprzedni wariant traktował nauczycieli ogólnych i WF jako jedną kategorię „spoza grupy”. To nie gwarantowało kolejności fallbacku. Dodatkowo szybkie szkice mogły czasowo poluzować prefer_home_group; v5.62 już tego nie robi.

## Architektura constraintów
- prefer_home_group: cp_sat_lexicographic,
- lokalne zakazy typu lekcja/blokada/dzień bez lekcji: candidate filter,
- tanie dowody konieczności: preflight,
- limity zbiorcze i relacje: CP-SAT hard,
- fairness/komfort: CP-SAT soft,
- post-guard tylko jako obrona przed regresją.

Rejestr constraint_architecture.py obejmuje wszystkie 23 globalne constrainty i jest sprawdzany testem regresji.

## Testy i wydajność
- pełna regresja: 186/186 testów OK,
- Python compile: OK,
- JavaScript syntax: OK,
- real-state performance gate: OK,
- dwa przebiegi: 80/80 dla 1–3 i 385/385 dla szkoły, missing=0,
- human guardrails: OK,
- 1–3: 78 własna grupa, 2 nauczyciele ogólni, 0 WF,
- czasy: 19.436 s i 21.204 s,
- mediana: 20.32 s.

WF pozostaje legalnym fallbackiem, ale jeżeli ten sam minimalny poziom obsady da się uzyskać nauczycielem ogólnym, CP-SAT wybiera nauczyciela ogólnego.
