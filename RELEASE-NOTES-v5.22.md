# DEMO Dyżury v5.22

## Interfejs
- Usunięto z głównych widoków pojedyncze, wyrwane z kontekstu limity dzienne oraz mylące teksty o oczekiwaniu.
- Usunięto duplikat przycisków awaryjnego rozszerzania puli przy brakach 1–3.
- Opisy pul są zgodne z zasadą comfort-first; grupa nauczyciela nie jest głównym kryterium.
- Ustawienia wymaganej obsady całej szkoły przeniesiono do Planowania zaawansowanego obok ustawień 1–3.
- Uporządkowano nazewnictwo użytkowe i zaktualizowano opis workera do v1.6.
- Diagnostyka wyjaśnia etapowe przeszukiwanie pełnych zakresów parametrów i kombinacji oraz pracę zdalnych workerów.

## Wersjonowanie
- Jedno źródło wersji: PLANNER_VERSION w app.py.
- /api/config publikuje app_meta; HTML i document.title pobierają wersję dynamicznie.
- FastAPI korzysta z PLANNER_VERSION.
- start_service.cmd używa własnego katalogu (%~dp0), bez numeru wersji w ścieżce.

## Solver
- solver_ortools.py bez zmian względem v5.21.
- Na tej samej kopii aktualnego stanu v5.21 i v5.22: identyczne 78/95 + 342/354 (29 braków) w gołym przebiegu bieżącej konfiguracji.
- Generator wariantów nadal testuje pełne dopuszczalne zakresy limitów, wszystkie rozszerzenia pul i kombinacje 1–5 zmian, etapami.
- Twardy zakaz wait >= 2 pozostaje bez zmian.

## Testy
- Python compile: OK.
- Headless UI: 8/8 zakładek bez błędów JS.
- Solver hash identyczny z v5.21.
