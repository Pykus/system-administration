# DEMO Dyżury v5.21

## Solver i wygoda
- Twardy filtr: kandydat wymagający oczekiwania >= 2 okresy lekcyjne nie trafia do modelu, nawet po zmiękczeniu avoid_wait.
- Kandydaci do puli 1–3 są oceniani najpierw po realnych slotach bez oczekiwania, nie po przynależności do grupy 1–3.
- Szybki probe szuka nowej pojemności wśród osób nieużywanych przez obie aktywne pule, żeby nie przenosić braków z 1–3 do całej szkoły.
- Każdy pełny wariant przechodzi osobną optymalizację komfortu przed pokazaniem użytkownikowi.
- Ranking pełnych wariantów: off-day -> suma oczekiwania -> liczba dyżurów z oczekiwaniem -> koszt organizacyjny -> liczba zmian.
- Generator utrzymuje do 12 pełnych finalistów zamiast 5.

## Parametry
- 3 wewnętrzne workery CP-SAT pozostają wartością domyślną i zalecaną.
- max_week migruje jednorazowo z dawnej domyślnej wartości 9 do 10. Późniejsza ręczna zmiana użytkownika nie jest nadpisywana.
- Constrainty globalne i indywidualne należą do profilu ustawień.

## Profile
- Eksport wybranego profilu do pliku JSON.
- Import profilu z pliku JSON.
- Profil nie zawiera planu dyżurów ani ręcznych przydziałów.

## Worker v1.6
- Samowystarczalny EXE.
- Polling kolejki co 10 s.
- Domyślnie 3 workery CP-SAT.
- Ten sam twardy filtr oczekiwania >=2.
- Brak autostartu; ręczne START-WORKER.cmd i STOP-WORKER.cmd.

## Test release
- realna kopia stanu: 95/95 dla 1–3 i 354/354 dla całej szkoły,
- max_wait=1, wait_ge2=0,
- headless UI: 8/8 zakładek bez błędów JS,
- Python compile: OK,
- profil import/export: OK,
- worker --self-test: OK.
