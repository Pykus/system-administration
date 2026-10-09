# DEMO Dyżury v5.8 — 2026-09-19

## Najważniejsze zmiany
- Semantyka „przed lekcją” została poprawiona: dotyczy wyłącznie przerwy przed pierwszą lekcją nauczyciela danego dnia.
- Przerwa dłuższa niż 5 minut przed pierwszą lekcją oraz po ostatniej lekcji jest stałym zakazem (hard, priorytet 5).
- Przerwa 5-minutowa przed pierwszą i po ostatniej lekcji ma osobny, opcjonalny constraint.
- Dodano osobną proporcjonalność do liczby lekcji w tygodniowym planie.
- Ręczna waga udziału w dyżurach pozostaje osobnym mechanizmem. Jeśli oba są aktywne, współczynnik z planu jest mnożony przez ręczną wagę.
- Tabela obciążenia pokazuje: liczba lekcji / tydzień, współczynnik z planu, ręczna waga, efektywny współczynnik.
- Panel nauczyciela łączy lekcje i dyżury w jednej tabeli czasu oraz pokazuje godziny lekcji i przerw.
- Widok zbiorczy pokazuje 15 nauczycieli na stronę zamiast 12.
- Ujednolicono i doprecyzowano opis wymaganej obsady 1–3 oraz całej szkoły: obie macierze są ustawieniami wejściowymi solvera, nie wynikiem.
- W całej szkole „0 — brak stanowiska” oznacza, że solver nie tworzy stanowiska dyżurowego w danym miejscu i na danej przerwie.

## Stan po wdrożeniu
- produkcja: http://127.0.0.1:8091
- dostęp: tylko localhost
- backend: 5.8 / OR-Tools CP-SAT
- bieżący zapisany plan został zachowany; wdrożenie nie podmieniło przydziałów automatycznie
- nowe twarde zasady obowiązują przy następnym przeliczeniu

## Ważne
Próbne przeliczenie 1–3 z nowymi zakazami i obecną pulą nauczycieli dało 91/95 stanowisk, czyli 4 braki. Nie rozluźniono automatycznie nowych zakazów i nie włączono awaryjnie nauczycieli ogólnych.
