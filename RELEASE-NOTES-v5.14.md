# DEMO Dyżury v5.14 — 2026-09-19

## Generator wariantów
- Zastąpiono szerokie brute-force wyszukiwanie beam searchem opartym o rzeczywiste wyniki częściowe.
- Screening jest krótki i służy wyłącznie do rankingu; nie jest już traktowany jako dowód braku rozwiązania.
- Najlepsze częściowe i nierozstrzygnięte warianty są ponownie sprawdzane z limitem 15–60 s.
- Dodatkowe oczekiwanie pozostaje absolutnie ostatnim etapem.
- Każda próba jest zapisywana w data/repair_jobs/<job>.jsonl, a bieżący stan/best partials w JSON checkpoint.
- Po restarcie UI potrafi pokazać ostatni zapisany checkpoint jako przerwany, zamiast utraty historii.
- Pełny wynik z głębokiej próby jest zachowywany razem z przydziałami; nie jest liczony drugi raz.
- Ranking mocno karze zmniejszenie wymaganej liczby stanowisk; 354/354 ma pierwszeństwo przed 353/353.
- Test na bieżących danych: gsoft:avoid_wait -> 95/95 + 354/354 w ok. 12 s; testowy beam search znalazł 7 pełnych wariantów przed zatrzymaniem ostatniej próby.

## UI
- Zakładka „Cała szkoła” ma klikalną sekcję „Braki” analogiczną do 1–3: dzień, slot, miejsce, legalni kandydaci i przyczyny odrzucenia.
- Diagnostyka pokazuje 10 najlepszych wyników częściowych, fazę, źródło i czas.
- Pokazywana jest liczba głębokich weryfikacji.

## Workery
- Broker pozostaje 192.0.2.10:8093, protokół workerów 5.12; Worker v1.1 jest zgodny.
- Reguła firewalla jest uznawana za poprawną tylko gdy obejmuje 198.51.100.29.0/24 i 192.0.2.0.0/16 oraz profil Public.
- Włączanie brokera potrafi idempotentnie naprawić tę regułę przez UAC.
- Gotowa paczka: DEMO-DutySolver-Worker-v1.1-r2.zip (sprawdzony EXE + DIAGNOZA-WORKERA.cmd).
- Nowo zbudowany eksperymentalny v1.2 został zatrzymany przed dystrybucją, ponieważ Enterprise WDAC na NODE00 blokuje nowy niepodpisany binarny plik; nie osłabiano polityki bezpieczeństwa.
