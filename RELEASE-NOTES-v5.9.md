# DEMO Dyżury v5.9 — 2026-09-19

- Odblokowano edycję reguł „przed pierwszą” i „po ostatniej” dla przerw >5 min: mogą być włączane/wyłączane i zmieniane MUSI BYĆ ↔ ZALECANE.
- Usunięto niejednoznaczne nazwy reguł indywidualnych „przed lekcją/po lekcji”; dotyczą teraz jawnie tylko pierwszej/ostatniej lekcji dnia.
- „Plany nauczycieli” mają jedną tabelę czasu z godzinami lekcji i przerw oraz checkbox „pokaż dyżury” przy każdym nauczycielu.
- Statystyki mają sortowanie po każdej kolumnie, filtry kolumnowe i zwężone kolumny liczbowe.
- Edycja bieżącego planu szkoły tworzy stały przydział administratora (locked_assignment) i zapisuje go razem z planem.
- Stałe przydziały administratora są widoczne w panelu nauczyciela; preferencja dla takiego slotu jest zablokowana.
- Preferencje nauczycieli są widoczne w sekcji edycji planu administratora i mogą być tam neutralizowane.
- Twarda preferencja „zabroniona” może pojawić się w propozycjach naprawczych solvera jako kandydat do usunięcia.
- Kolejność constraintów nie decyduje o dopuszczeniu nauczyciela: twarde warunki filtrują kandydatów, kolejność rozstrzyga jedynie miękkie reguły o tym samym poziomie.

## Audyt konfiguracji przed wdrożeniem
- Zapisany plan: 23 nauczycieli z 0 dyżurów, maksimum 10.
- Symulacja z workload_fairness=MUSI BYĆ: 1–3 = 0/95; reguła faktycznie blokowała rozwiązanie.
- Symulacja z workload_fairness=ZALECANE: 1–3 = 91/95; liczba nauczycieli z 0 dyżurów w nowym wyniku spada do 2.
- Dlatego wykonano jednorazową migrację bieżącego workload_fairness z MUSI BYĆ na ZALECANE: True.
- Pozostałe 4 braki 1–3 blokuje twarda reguła dodatkowego oczekiwania; nie zmieniono jej automatycznie.
- Długie przerwy jako MUSI BYĆ powodują 3 braki w całej szkole; po zmianie tych reguł na ZALECANE symulacja daje 354/354. Reguły są od v5.9 normalnie edytowalne.
