# Zasady UI i wersjonowania

1. Numer aplikacji ma jedno źródło: `PLANNER_VERSION` w app.py.
   UI pobiera wersję z /api/config -> app_meta.version; nie wpisujemy numeru wersji na sztywno w HTML/JS/CMD.
2. Skrypty startowe używają własnego katalogu (%~dp0), bez ścieżek zawierających numer wersji.
3. Widoki użytkowe (1–3, cała szkoła, plany nauczycieli) pokazują wynik i czynności użytkownika,
   a nie przypadkowo wybrane parametry solvera.
4. Wszystkie reguły/limity konfigurujemy w Planowaniu zaawansowanym. Diagnostyka może pokazywać
   techniczne szczegóły wyszukiwania i workerów.
5. Analogiczne ustawienia obu zakresów powinny znajdować się razem; nie duplikujemy przycisków
   wykonujących tę samą czynność w jednym widoku.
6. Generator wariantów opisujemy jako etapowe, systematyczne przeszukiwanie pełnych zakresów
   dostępnych parametrów i kombinacji. Nie sugerujemy, że jedna reguła steruje całym zachowaniem.
7. Kryterium rozszerzania pul jest comfort-first: realna dostępność i brak dodatkowego oczekiwania
   są ważniejsze niż kategoria/grupa nauczyciela.

## v5.77 single source-of-truth rule

Every screen displaying duties renders the same backend effective-plan and the same
source_id. JavaScript must not choose its own solver variant.

reference_verified must be visibly labeled as a reference plan. invalid_saved must not
use success styling and must show backend audit filled/required counters.
