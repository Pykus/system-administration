# DEMO Dyżury v5.23

## Priorytet wyszukiwania
- Etap 1 musi zostać wyczerpany przed jakimkolwiek pogorszeniem komfortu nauczycieli.
- Etap 1 obejmuje limity organizacyjne max_day_13, max_day_school, max_week, rozszerzanie pul i przenoszenie osób między pulami.
- Test sufitu jest tylko diagnostyczny i nie może przeskoczyć etapu.
- Etap 2: łagodne reguły komfortu.
- Etap 3: mocne reguły komfortu, długie przerwy, wydłużanie dnia, preferencje/blokady.
- Etap 4 jest absolutnie ostatni: dodatkowe oczekiwanie oraz 3+ kolejne dyżury.
- Twardy zakaz oczekiwania >=2 okresy pozostaje niezmieniony.

## Parametry numeryczne
- Podczas searchu limity mogą być podnoszone dla wykonalności.
- Po znalezieniu pełnego planu podniesione limity są automatycznie zacieśniane do najmniejszej wartości potrzebnej przez znalezione przypisania.
- Wymagana obsada stanowisk nie jest automatycznie obniżana.

## Workery
- Node00 nie jest już liczony jako zdalny worker farmy.
- Panel pokazuje wszystkie zarejestrowane zdalne workery, także offline.
- Lista odświeża się co 2 sekundy.
- Wyniki częściowe pokazują użytkowe opisy zmian; tokeny są schowane w Szczegółach technicznych.

## Testy
- Python compile: OK.
- Test kolejności etapów: OK; stage 4 pojawia się dopiero po zakończeniu 1-3.
- Audyt realnych kandydatów: avoid_wait i max_consecutive >=3 wyłącznie stage 4.
- Test wielu workerów: endpoint zwrócił jednocześnie wiele zdalnych workerów.
- UI headless: 8/8 zakładek bez błędów JS.
- Deterministyczna regresja solvera: v5.22 i v5.23 identycznie 18 braków na tym samym aktualnym stanie.
- solver_ortools.py: identyczny hash z v5.22.
