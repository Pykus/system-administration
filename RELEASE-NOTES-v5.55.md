# RELEASE NOTES v5.55 — jasne minimum i kandydaci dla długich przerw

- Rozdzielono trzy różne pojęcia, które wcześniej były pokazane razem: udowodnione minimum, kandydaci oraz faktyczny stan konkretnego szkicu.
- Dla długiej przerwy po ostatniej lekcji i przed pierwszą lekcją szybki preflight liczy dolną granicę: co najmniej ilu różnych nauczycieli i ile przydziałów wyjątkowych jest naprawdę koniecznych z powodu wymaganej obsady.
- Lista kandydatów pochodzi z porównania wykonalności tej samej obsady przy regule HARD oraz SOFT; pokazuje nauczycieli, którzy stają się legalni właśnie po poluzowaniu tej jednej reguły.
- Jeśli preflight nie wykazuje konieczności wyjątku, interfejs mówi wprost, że nie ma udowodnionego minimum > 0 i że solver powinien dalej usuwać taki kompromis.

- Dane szkicu są teraz opisane jako stan szkicu, a nie minimum: liczba faktycznie obciążonych nauczycieli, liczba przydziałów oraz liczba różnych długich przerw.
- Dodano rozkład po konkretnych długich przerwach, dzięki czemu widać, że jedna przerwa może wymagać kilku równoległych stanowisk i wygenerować kilka przydziałów.
- Lista osób pod stanem szkicu jest jawnie opisana jako lista osób faktycznie przydzielonych, a nie lista kandydatów.

- Na aktualnym stanie testowym preflight nie wykazał konieczności ani jednego wyjątku dla długiej przerwy po ostatniej lekcji, mimo że pierwszy pełny szkic miał wiele takich przydziałów. To potwierdza, że poprzednia prezentacja mogła sugerować coś, czego matematycznie nie udowodniono.

Gate: 124/124 testów OK, Python compile OK, JS syntax OK, staging health v5.55 OK.