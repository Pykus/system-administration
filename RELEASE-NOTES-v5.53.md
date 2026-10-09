# RELEASE NOTES v5.53 — preflight niewykonalnych constraintów

## Zasada nadrzędna
- Preflight nie zmniejsza wymaganej obsady z powodu constraintu.
- Automatyczne ustawienie obsady na 0 jest dozwolone wyłącznie, gdy plan lekcji pokazuje, że dana strefa/korytarz/piętro nie jest już aktywne.
- Jeżeli pełna obsada jest matematycznie niemożliwa przy regule użytkownika ustawionej jako „Musi być”, preflight najpierw dowodzi niedoboru i zmienia wyłącznie tę regułę na „Zalecane 5 — Najwyższa”.
- Komunikat pokazuje regułę, minimalną liczbę koniecznych wyjątków oraz sloty, w których powstaje niedobór.

## Co preflight potrafi udowodnić bez CP-SAT
- Dopasowanie stanowisko↔nauczyciel w każdym slocie z uwzględnieniem twardych kolizji.
- Reguły przed pierwszą / po ostatniej lekcji, krótkie i długie przerwy oraz dodatkowe oczekiwanie.
- Indywidualne zakazy przed pierwszą i po ostatniej lekcji.
- Dolne granice limitów dziennych, tygodniowych i długich przerw.
- Konieczność kolejnych dyżurów przez dopasowanie łączne dwóch sąsiednich przerw.
- Mały pełny przegląd kombinacji reguł brzegowych wybiera najmniej kosztowy zestaw koniecznych ustępstw.

## Reguły, których preflight nie luzuje automatycznie
- kolizja z lekcją,
- maksymalnie jedno miejsce w slocie,
- konflikt zakresów 1–3 / szkoła,
- ręczne blokady administratora,
- dyżur w dniu bez lekcji.
Takie przypadki są raportowane jako rzeczywisty blocker.

## Oszczędzanie czasu solvera
Jeżeli po dopuszczalnych automatycznych korektach preflight nadal dowodzi, że slot jest niewykonalny, pełny CP-SAT nie jest uruchamiany.

## Pozostałe poprawki odziedziczone z v5.52
- zwykły widok planu nie pokazuje roboczego wariantu Generatora poza Diagnostyką,
- dodatkowa walidacja podwójnych przydziałów i duplikatów stanowisk,
- eksport PDF całej szkoły: jeden dzień na jednej stronie A4 landscape, bez dzielenia na części, węższe kolumny i wyrównanie treści do lewej,
- procesy usługi/brokera są zamykane wraz z drzewem procesów; nowe wdrożenie nie używa trwałych okien CMD.

## Testy
Nowe testy obejmują minimalny koszt kombinacji constraintów, indywidualne wyjątki po ostatniej lekcji, limity pojemności, zakaz redukcji obsady z powodu constraintu oraz trwałość automatycznego złagodzenia.
