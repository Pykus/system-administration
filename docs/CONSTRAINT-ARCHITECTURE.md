# Architektura constraintów planera dyżurów — v5.62

## Zasada wyboru warstwy
1. Prosty warunek nauczyciel–pozycja (np. kolizja z lekcją, ręczna blokada, dzień bez lekcji) → filtr kandydatów w Pythonie. Nie warto tworzyć zmiennej CP-SAT dla krawędzi, która z góry jest nielegalna.
2. Warunek konieczny, który da się tanio udowodnić przed solverem → preflight. Preflight ma odpowiadać „czy to w ogóle możliwe?” i „jaki minimalny wyjątek jest nieunikniony?”, ale nie ma zastępować globalnej optymalizacji.
3. Relacja między wieloma przydziałami / limit zbiorczy → twardy constraint CP-SAT.
4. Strukturalna preferencja o wyraźnym pierwszeństwie → osobny etap leksykograficzny CP-SAT po pełnej obsadzie. Tak działa od v5.62 „właściwa grupa najpierw”.
5. Jakość/komfort wymagająca globalnego kompromisu → soft objective CP-SAT.
6. Post-guard → wyłącznie obrona przed regresją lub patologicznie słabym szkicem. Nie może być jedyną implementacją ważnej reguły.

## 23 constrainty i warstwa główna
| Constraint | Główna warstwa | Uzasadnienie |
|---|---|---|
| no_lesson_overlap | candidate_filter | pojedyncza krawędź jest fizycznie niemożliwa |
| one_place_per_slot | cp_sat_hard | sprzęga równoległe pozycje |
| cross_scope_conflict | cp_sat_hard | sprzęga 1–3 i całą szkołę |
| manual_blocks | candidate_filter | ręczny zakaz konkretnej krawędzi |
| preserve_school_current | repair_lexicographic | minimalna perturbacja w naprawie |
| max_day_13 | cp_sat_hard | limit zbiorczy |
| max_day_school | cp_sat_hard | limit zbiorczy |
| max_week | cp_sat_hard | limit zbiorczy człowieka |
| prefer_home_group | cp_sat_lexicographic | pełna obsada → minimum obcych grup → dla 1–3 minimum WF → reszta jakości |
| balance_day | cp_sat_soft | rozkład jakościowy |
| balance_week | cp_sat_soft | słabszy tie-breaker rozproszenia |
| max_long_day | cp_sat_hard | limit zbiorczy człowieka |
| max_long_week | cp_sat_hard | limit zbiorczy człowieka |
| after_last_short | candidate_filter + preflight/soft | relacja lokalna; soft jako koszt |
| after_last_long | candidate_filter + preflight/soft | relacja lokalna; preflight może dowieść wyjątku |
| preference_grid | cp_sat_soft | koszt krawędzi |
| zone_transition_penalty | cp_sat_soft | koszt krawędzi, liczony lokalnie |
| before_first_short | candidate_filter + preflight/soft | relacja lokalna |
| before_first_long | candidate_filter + preflight/soft | relacja lokalna |
| lesson_load_fairness | cp_sat_soft + post_guard | globalny udział proporcjonalny do lekcji × współczynnik |
| max_consecutive_duties | cp_sat_hard + preflight/post_guard | okna sąsiednich przerw |
| offday_duty | candidate_filter | brak lekcji w dniu czyni krawędź nielegalną |
| avoid_wait | candidate_filter + preflight/soft | oczekiwanie da się policzyć dla krawędzi; >=2 okresy jest systemowo zakazane |

## Audyt v5.62
- prefer_home_group nie powinien być twardym zakazem. Test rzeczywisty z HARD pozostawił 18 braków (8 w 1–3, 10 w całej szkole), więc nauczyciele spoza grupy są realnie potrzebnym fallbackiem.
- Historyczne soft priority 3 było za słabe wobec fairness priority 5. W realnym szkicu tylko 13 z 80 przydziałów 1–3 trafiało do nauczycieli 1–3, reszta głównie do nauczycieli ogólnych/WF.
- v5.62 ustawia tę regułę na soft priority 5 i po znalezieniu pełnej obsady uruchamia osobny etap CP-SAT: minimalizuj liczbę obcych grup. Dopiero potem optymalizowane są fairness i pozostałe koszty.
- Test na bieżącym stanie po zmianie: 80/80 + 385/385, 78 z 80 dyżurów 1–3 obsadzonych przez grupę 1–3, 2 przez grupę ogólną, 0 przez WF; human guardrails zachowane.

## Zasada dla przyszłych zmian
Nowy constraint przed implementacją musi mieć wpis w constraint_architecture.py. Test architektury porównuje rejestr z rzeczywistą listą globalnych constraintów, więc dodanie nowego constraintu bez decyzji o warstwie ma zepsuć regresję zamiast przejść niezauważone.
## Strukturalny fallback WF — v5.77

Historyczna zasada v5.62 „1–3 → ogólni → WF” została rozszerzona na cały Generator. WF nie jest implementowany jako zwykła waga `prefer_home_group`, lecz jako osobna faza wyszukiwania i osobny etap leksykograficzny CP-SAT.

Porządek kompromisów istotnych dla tej decyzji:
1. pełna obsada przez zwykłe przetasowania bez WF,
2. pozostałe legalne zmiany puli/limitów bez WF,
3. WF jako awaryjna faza 4,
4. `after_last_long` jako faza 5,
5. `avoid_wait` jako faza 6.

Fairness, zgodność grupy i estetyka rozkładu pozostają celami optymalizacji, ale nie mogą wymusić dodatkowego WF. Jeżeli WF jest konieczny, Solver minimalizuje łączną liczbę jego przydziałów; ręczne stałe przydziały administratora stanowią dozwolony baseline i nie są usuwane.

## v5.77 protected priority ladder

Protected stages are structural:
1. hard/system constraints and complete coverage;
2. ordinary pool moves, capacity and individual non-edge changes;
3. remaining limits, group preferences and fairness;
4. WF emergency fallback;
5. after_last_long;
6. avoid_wait as the absolute last fallback.

If a verified full plan exists at stage 4 or earlier, stage 5 is not opened merely to
produce more variants. Automatic WF assignments are minimized lexicographically in both
scopes; fixed administrator WF assignments are not counted as automatic fallback.


## v5.78 — kolejność przestrzenna i WF

Preferencja miejsca nie jest constraintem typu hard. Wartość 0 nadal pozostawia legalnego kandydata, lecz daje największy deficyt preferencji. Wartość 1 daje deficyt 0. Poziomy pośrednie: 0,25 / 0,50 / 0,75.

Twarde właściwości miejsca są niezależne od macierzy. `Sala gimnastyczna A/B` wymaga grupy WF; wpisanie wartości 1 nauczycielowi spoza WF nie omija tego ograniczenia.

Leksykograficznie Solver chroni pokrycie i reguły hard. Awaryjne WF poza miejscami WF-only są minimalizowane przed niedopasowaniem miejsca. Generator nie może poprawiać preferencji miejsca kosztem długiej przerwy po ostatniej lekcji. `avoid_wait` jest ostatnim etapem luzowania.

Stare tokeny rozszerzania pul mogą być rozpoznawane wyłącznie przy kompatybilności ze starymi zapisami; nowe wyszukiwanie ich nie generuje.
