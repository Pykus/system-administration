# Architektura DEMO Dyżury v5.4

## Stos
- FastAPI – API i serwowanie aplikacji.
- Vue 3 – interfejs użytkownika.
- Google OR-Tools CP-SAT – właściwy silnik planowania.
- JSON – stan roboczy, dane źródłowe, warianty i historia operacyjna.

## Model przydziałów
Dla każdej pary stanowisko–nauczyciel CP-SAT tworzy zmienną boolowską. Każde stanowisko otrzymuje dokładnie jednego nauczyciela albo zostaje jawnie oznaczone jako nieobsadzone.

Solver działa wieloetapowo:
1. minimalizuje liczbę braków,
2. przy tej samej liczbie braków optymalizuje stabilność planu w trybie naprawczym,
3. następnie minimalizuje koszty preferencji.

Dzięki temu preferencja miękka nie może być ważniejsza od możliwego obsadzenia dyżuru.

## Constrainty
„Musi być” jest ograniczeniem twardym lub eliminuje kandydaturę. „Zalecane” wpływa na funkcję celu.

Priorytety miękkie mają poziom 1–5. Kolejność listy jest dodatkowym rozstrzygnięciem dla reguł o tym samym poziomie. Kolejność reguł twardych jest wyłącznie porządkiem interfejsu, ponieważ wszystkie obowiązują równocześnie.

Stałe reguły systemowe nie mogą zostać wyłączone:
- nauczyciel nie dyżuruje podczas własnej lekcji,
- nie dyżuruje w dwóch miejscach równocześnie,
- ręczna blokada jest bezwzględna.

## Relacja dyżuru do lekcji
Przerwa pomiędzy dwiema lekcjami jest normalnie dozwolona.

Reguła „Zakaz dyżuru tylko przed lekcją” dotyczy sytuacji, w której nauczyciel ma lekcję tylko po przerwie.

Po ostatniej lekcji używane są dwie osobne reguły:
- `after_last_short` – krótka przerwa po ostatniej lekcji; domyślnie wyłączona,
- `after_last_long` – długa przerwa po ostatniej lekcji; domyślnie Zalecane, priorytet 4.

Osobny `avoid_wait` kontroluje dodatkowe oczekiwanie lub przychodzenie wcześniej tylko na dyżur.

## Długie przerwy
Długa przerwa jest rozpoznawana według progu minutowego (domyślnie 15 min). Źródłowy rozkład ma dwie 20-minutowe długie przerwy w każdym dniu.

- `max_long_day`: 0–2, domyślnie 1.
- `max_long_week`: 0–10, domyślnie 3.

Limity obejmują łącznie dyżury 1–3 i ogólnoszkolne danego nauczyciela.

## Planowanie zaawansowane
v5.3 wprowadziła:
- `teacher_workload` – współczynnik obciążenia/pensum,
- `preference_grid` – preferencje nauczyciela dla slotów,
- `location_zones` – koszt przejścia między strefami,
- `locked_assignments` – zamrożone przydziały,
- `absent_teachers` / `active_absences` – nieobecności,
- tryb naprawczy Minimal Perturbation – minimalizuje liczbę zmian wobec planu odniesienia,
- `solver_seed` i tryb deterministyczny,
- publikowany snapshot i plan operacyjny.

## Diagnostyka
Każde rozwiązanie zwraca diagnostykę CP-SAT: status, czas, braki, liczbę legalnych kandydatów i powody odrzucenia. Osobna karta Walidacji analizuje konfigurację przed solverem.

Walidacja sprawdza m.in. sprzeczne reguły twarde, nieistniejących nauczycieli/sloty, konflikty wymaganych dyżurów z lekcjami oraz zakresy limitów 0–2 i 0–10.

Diagnostyka może szukać minimalnego poluzowania konfigurowalnych reguł twardych. Stałe reguły systemowe nie są kandydatami do poluzowania.

## Zgodność i migracja
`ensure_state_schema()` migruje starszy stan do bieżącego schematu, normalizuje priorytety do 1–5, dopisuje brakujące pola i utrzymuje stałe reguły systemowe jako aktywne HARD.

v5.4 jest wersją scalającą: powstała z najnowszej v5.3 po wykryciu równoległej pracy innego wątku ChatGPT. Przed wdrożeniem porównywane są sumy SHA-256 plików bazowych, aby nie nadpisać nowszych zmian.



## v5.6 – rejestr nauczycieli i portal
Rejestr nauczycieli jest przechowywany w `data/teacher_registry.json`. Zawiera kategorię (`school`, `1-3`, `wf`), aktywność i trwały token portalu nauczyciela. `seed.json` nadal przechowuje plany lekcji; przy starcie aplikacji kategoria z rejestru jest nadrzędna.

Import planów PDF aktualizuje istniejących nauczycieli, a nowe nazwiska dodaje automatycznie. Wstępna klasyfikacja korzysta z przedmiotów WF oraz udziału zajęć w klasach rozpoznanych jako 1–3. Administrator może później ręcznie zmienić kategorię.

Portal `/teacher?t=<token>` korzysta wyłącznie z endpointów `/api/teacher-portal/{token}` i `/api/teacher-portal/{token}/preferences`. Zwracają one tylko dane konkretnego nauczyciela: jego lekcje, dyżury i siatkę preferencji.

## Kolejność zasad
Reguły „Musi być” są nakładane równocześnie, więc ich położenie na liście nie ma znaczenia dla wykonalności. Dla reguł „Zalecane” podstawą jest poziom 1–5, a kolejność listy jest drobnym tie-breakerem dla reguł na tym samym poziomie. Kolejność listy jest zapisywana w `state.json`.

## Strefy 1–10
Wartość strefy jest umowną pozycją na osi od blisko do daleko. Solver używa różnicy wartości jako względnego kosztu przejścia: 2→3 jest małą różnicą, 2→9 dużą. Jest to model porównawczy, nie czas przejścia w minutach.

- Pula „cała szkoła” jest filtrowana w backendzie: nauczyciele grupy 1–3 nie mogą otrzymać dyżuru ogólnoszkolnego; nauczyciele ogólni mogą być użyci pomocniczo w 1–3.

## Mapa sal / API obłożenia (v5.60.1)
Endpoint GET /api/map/lessons buduje read-only indeks planu z SEED["teachers"][*]["lessons"]. Kluczem jest numer/oznaczenie sali, następnie dzień i numer lekcji. occupied_slots jest liczbą unikalnych par dzień+lekcja dla sali; total_slots=45 (5 dni × 9 lekcji).

Frontend static/map.html przechowuje wyłącznie geometrię kondygnacji. Po załadowaniu pobiera plan z API, wylicza intensywność heat mapy z occupancy oraz buduje modal planu sali. Inwentaryzacja urządzeń nie jest częścią tego widoku.

## Ochrona aktywności strefy 1–3 (v5.60.2)
Funkcja _position_zone_active_13 pozostaje źródłem prawdy dla istnienia stanowisk 1–3. Aktywność trwa przez przerwy wewnętrzne oraz przerwę bezpośrednio po ostatniej lekcji, ale nie dalej.

_sanitize_inactive_13_state zeruje min_people_13/min_people_13_stations dla nieaktywnych slotów, usuwa require_slot o zakresie 1–3 i czyści zapisane przydziały w tych slotach. required_slot_rules ma niezależny filtr obronny. _set_required_13_count oraz endpoint obsady stanowisk nie pozwalają ustawić dodatniej obsady w nieaktywnej strefie.

## Hierarchia awaryjna WF (v5.77)

Kategoria `wf` nie jest zwykłym członkiem automatycznej puli. W fazach podstawowych Solver usuwa WF z puli roboczej, nawet jeśli nauczyciele WF są zapisani w `enabled_teachers_school` lub `enabled_teachers_13`. Wyjątkiem są stałe przydziały administratora — wskazany ręcznie nauczyciel WF pozostaje legalny i wymagany.

Kolejność wyszukiwania jest strukturalna: organizacja bez WF → ustępstwa indywidualne bez WF → limity i preferencje bez WF → awaryjny WF → `after_last_long` → `avoid_wait`. WF jest zatem chroniony mocniej niż zwykła sprawiedliwość, grupa czy koszt przetasowania, ale słabiej niż długa przerwa po ostatniej lekcji.

Po odblokowaniu fazy WF osobny etap leksykograficzny CP-SAT minimalizuje liczbę przydziałów WF w obu zakresach. Live-gate wymaga zarówno jawnego odblokowania fazy WF, jak i statusu OPTIMAL dla minimum WF w każdym zakresie, w którym WF został użyty.

## v5.77 canonical effective-plan

The /api/effective-plan endpoint is the only source of duty assignments for the admin
plan, statistics, diagnostics and teacher portal. Frontend code must not independently
choose a repair variant or infer completeness from row counts.

Source precedence is: verified live result, verified saved plan, revalidated
data/last_good_plan.json reference, then invalid_saved with an explicit audit.
The audit counts real assigned teachers and checks cross-scope slot collisions.


## v5.78 — canonical place-preference model

Kanonicznym modelem przestrzennym jest `teacher_place_preferences[teacher][place_key]`. Każdy aktywny nauczyciel jest widoczny dla modelu CP-SAT; historyczna grupa nauczyciela służy jedynie do inicjalizacji macierzy. Generator nie tworzy już nowych kombinacji przez rozszerzanie pul.

`duty_places` jest jedną listą miejsc. Pola `legacy_scope` zachowują zgodność ze starszymi formatami 1–3 / school, ale nie definiują puli ludzi. Właściwość `exclusive_group` jest twarda i stoi ponad macierzą preferencji.

Dwa miejsca systemowe `Sala gimnastyczna A/B` mają `zone=gym`, `exclusive_group=wf`. Szkolny solve jest dekomponowany: najpierw miejsca gym, potem pozostałe miejsca z przydziałami gym jako stałymi `other_assignments`. Dzięki temu limity dnia/tygodnia i kolizje pozostają globalne, a przestrzeń wyszukiwania jest mniejsza.

Macierz oraz `duty_location_zones` są częścią podpisu wejścia Solvera i fingerprintu learningu.
