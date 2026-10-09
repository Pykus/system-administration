# RELEASE NOTES v5.60.2 — ochrona wygaszonej strefy 1–3

## Przyczyna
Dwa stare skrypty integracyjne test_v44.py i test_require.py wykonywały mutacje bezpośrednio na produkcyjnym API 127.0.0.1:8091. Dodawały twarde require_slot na Wt 9/po odpowiednio dla Piotra Wiśniewskiego i Anny Nowickiej. Ich sekcja finally zapisywała kopię stanu do katalogu v5.1, więc nie odtwarzała bieżącej produkcji.

## Naprawa
- plan lekcji pozostaje nadrzędnym źródłem aktywności strefy 1–3;
- po ostatniej przerwie bezpośrednio po ostatniej lekcji strefa jest nieaktywna;
- nieaktywny slot 1–3 ma zawsze obsadę 0, niezależnie od żądania API;
- require_slot o zakresie 1–3 dla nieaktywnego slotu jest usuwany przy zapisie/odczycie stanu;
- solver dodatkowo ignoruje takie wymuszenie nawet w niesanitarnym obiekcie wejściowym;
- zapisane stare przydziały 1–3 w nieaktywnym slocie są czyszczone.

## Live gate
Po wdrożeniu 5.60.2:
- health = 5.60.2;
- validation errors = 0;
- Wt 9/po = 0 osób, A=0, B=0;
- próba dodania dwóch nowych hard require_slot na Wt 9/po przez produkcyjne API: 0 reguł przetrwało;
- próba ustawienia obsady Wt 9/po na 2: wynik pozostaje 0.
