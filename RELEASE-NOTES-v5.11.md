# DEMO Dyżury v5.11 — 2026-09-19

- NODE00 wykonuje równolegle wiele prób generatora; domyślnie 4 lokalne zadania, regulowane 1–8.
- Zdalne workery są opcjonalne i używają osobnego brokera LAN na TCP 8093. Planer na 8091 pozostaje localhost-only.
- Broker jest domyślnie wyłączony; uruchamia się dopiero po wybraniu „Umożliw pracę zdalnym workerom”.
- Raport workerów pokazuje online/idle/busy/offline, aktualne tokeny zadania, czas bieżącego zadania, ukończone zadania, błędy i średni czas.
- Wyszukiwanie ma pięć etapów. Unikaj dodatkowego oczekiwania jest wyłącznie etapem 5/5 i nie jest mieszane z wcześniejszymi pulami.
- Warianty z poluzowaniem oczekiwania są dodatkowo sortowane na końcu listy.
- Przegląd każdego wariantu jest zwijalny bezpośrednio w jego karcie.
- Puste karty są ukrywane przez CSS.
- Worker EXE ma być samowystarczalny, automatycznie odkrywać NODE00 i weryfikować wersję planera oraz hash danych źródłowych.
