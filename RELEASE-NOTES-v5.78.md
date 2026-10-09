# v5.78 — macierz nauczyciel × miejsce dyżuru

## Nowy model przydziałów

- Sztywne pule nauczycieli nie sterują już Solverem. Etykiety `1–3`, `ogólny` i `WF` służą wyłącznie do nadania wartości początkowych.
- Każdy aktywny nauczyciel ma osobną preferencję dla każdego konkretnego miejsca dyżuru: `0 / 0,25 / 0,50 / 0,75 / 1,00`.
- `0` oznacza kosztowny fallback, a nie twardy zakaz. Twarde blokady administratora i właściwości miejsca są osobnym mechanizmem.
- CP-SAT minimalizuje awaryjne użycie WF poza miejscami sportowymi, a następnie koszt niedopasowania nauczyciel × miejsce.
- Zmiana macierzy jest częścią podpisu wejścia Solvera i unieważnia stare wyszukiwanie.

## Miejsca dyżuru

- Zakładka **Miejsca dyżurów** ma jedną listę wszystkich punktów zamiast osobnych paneli dla 1–3 i całej szkoły.
- Usunięto z interfejsu karty „Pula kandydatów”.
- Dodano systemowe miejsca **Sala gimnastyczna A** i **Sala gimnastyczna B**.
- Oba miejsca są twardo ograniczone do nauczycieli WF.
- Aktywność sali wynika z rzeczywistego planu: kody `sg*` i `sił` oznaczają strefę sportową; `kor` nie jest traktowany jako sala.
- A/B wymagają po jednej osobie na przerwie bezpośrednio przed lub po lekcji w strefie sportowej.
- WF przydzielony na A/B nie jest liczony jako awaryjne użycie WF.
- Solve szkoły najpierw rozwiązuje ekskluzywne A/B, a następnie resztę szkoły z tymi przydziałami jako zamrożonymi `other_assignments`.

## Spójność i priorytety

- Wszystkie aktywne osoby są widoczne dla CP-SAT od początku; Generator nie rozszerza już pul tokenami `addschool/add13group`.
- `after_last_long` pozostaje chroniony przed zwykłymi preferencjami miejsca i fairness.
- `avoid_wait` pozostaje ostatnim fallbackiem Generatora.
- Zapisany lub live plan jest uznawany za pełny tylko po audycie realnie przypisanych nauczycieli.

## Walidacja kandydata

- pełna regresja po zmianach architektury: 313 testów,
- testy A/B: dwa różne nazwiska WF w tym samym slocie,
- realny model: 80 wymaganych pozycji 1–3 + 475 szkoły = 555,
- realny pełny plan testowy: 555/555, A/B 90/90, 0 awaryjnych WF poza salą, 0 `after_last_long`.
