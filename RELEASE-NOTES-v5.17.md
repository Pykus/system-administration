# DEMO Dyżury v5.17

## Naprawy
- Naprawiono pusty ekran po wejściu w „Planowanie zaawansowane”.
- Przyczyna: helper sortowania nazwisk `sortNames()` został omyłkowo dodany tylko do komponentu macierzy, a sekcja zaawansowana wywoływała go w głównej aplikacji.
- Usunięto zbędne skróty „Zmień zasady przydziału” z górnych paneli 1–3 i całej szkoły.
- Odtworzono v5.17 z czystej v5.16, eliminując uszkodzone kodowanie z wcześniejszej roboczej kopii.
- Poprawna deklaracja FastAPI: `version="5.17"`.

## Solver
- Domyślna liczba wewnętrznych workerów CP-SAT: 3, zgodnie z benchmarkiem Solver Lab.
- Nadal można nadpisać parametr w stanie/testach.

## Warunek wdrożenia
- Python compile.
- JavaScript syntax.
- Headless UI smoke dla wszystkich głównych zakładek.
- Pełny solve / missing=0 na realnej kopii stanu.
- Rollback do v5.16.

## Hotfix 2026-09-20
- Vue runtime served locally for UI bootstrap.
- Broker root / returns health instead of 404.
