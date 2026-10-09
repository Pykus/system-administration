# RELEASE NOTES v5.50 — spójność constraintów i obsady stref

## Krytyczna poprawka obsady
- Strefa pozostaje aktywna na przerwie bezpośrednio po lekcji kończącej się w tej strefie.
- Dotyczy korytarza 1–3 oraz stref całej szkoły: parter, I piętro, II piętro.
- Jeśli po kończącej się lekcji strefa miałaby 0 obsady, system wymaga minimum 1 osoby.
- Punkt „wejście” ma wymaganą obsadę 1 przez cały aktywny dzień szkolny: od przerwy przed pierwszymi lekcjami do przerwy bezpośrednio po ostatniej lekcji danego dnia.
- Ręczne zmniejszenie obsady 1→0 w aktywnej strefie lub przy wejściu zwraca ostrzeżenie i wymaga jawnego potwierdzenia.
- Potwierdzone ręczne zero jest zapisywane jako świadomy wyjątek i nie jest automatycznie cofane.
- Migracja odświeża required_people/complete zapisanych wierszy 1–3 bez zmiany nauczycieli.

## Porządkowanie constraintów
- Usunięto „Dyżur przy własnej lekcji” (adjacent_lesson); pozostaje „Unikaj dodatkowego oczekiwania”.
- Usunięto „Ograniczaj kumulację długich przerw” (long_break_penalty); długą przerwą pozostaje systemowo >=15 min, a działają limity max_long_day/max_long_week.
- Usunięto osobny workload_fairness.
- Jeden mechanizm fairness: „Sprawiedliwy podział wg obciążenia dydaktycznego”.
  Docelowy udział = liczba lekcji w tygodniu × ręczna korekta teacher_workload.
- Migracja zachowuje na wspólnym fairness najsilniejszy aktywny priorytet starych dwóch reguł; dla produkcyjnego stanu v5.49 daje Zalecane / priorytet 5.
- „Unikaj dalekich przejść między strefami” zmieniono na „Preferuj dyżur blisko sali lekcyjnej”.
  Dla numerowanych sal/miejsc używana jest także heurystyka pierwszej cyfry numeru.
- Preferencje nauczyciela: tylko Preferowana / Neutralna / Niepożądana.
- Stare forbid są migrowane do avoid; twarde „nie mogę” pozostaje blokadą administratora.

## TDD
- Nowe testy v5.50: 12.
- Pełny gate przed wdrożeniem: 89/89 OK.
- Python compile: OK.
- Vue/JS syntax: OK.
- Audyt wszystkich dni i stref po migracji: 0 naruszeń wymaganej minimalnej obsady.
