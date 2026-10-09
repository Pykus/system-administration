# DEMO Dyżury v5.7 — 2026-09-19

## Wdrożone
- minimalna obsada całej szkoły: macierz 0/1 dla każdego miejsca, dnia i przerwy,
- edytowalna lista miejsc dyżuru; migracja zachowała 11 miejsc ze źródłowego/bieżącego planu,
- + nauczyciele ogólni przy puli 1–3,
- warianty naprawcze: najpierw Przejrzyj wariant, dopiero potem zastosowanie,
- kopiowanie linku nauczyciela ma fallback dla zwykłego HTTP,
- Sloty lekcji -> Lekcji w planie,
- Przelicz wszystko odświeża również listę nauczycieli, miejsca i obie macierze obsady,
- diagnostyka jest bardziej zwarta; szczegóły techniczne pozostają rozwijane,
- test regresyjny 9/po: ustawienie 1 oznacza dokładnie jedno wymagane stanowisko.

## 9/po
W produkcyjnych danych wszystkie pięć 9/po ma obsadę minimalną = 1. Solver liczy to poprawnie:
50 przerw 1–3 po dwa stanowiska dałoby 100 pozycji, a pięć 9/po po jednym daje łącznie 95 wymaganych pozycji.

Braki na 9/po wynikają obecnie z twardej zasady Unikaj dodatkowego oczekiwania. Po dodaniu nauczycieli ogólnych tylko wtorek ma osobę z lekcją bezpośrednio przed tą przerwą; w pozostałe dni kandydaci musieliby czekać dodatkową lekcję. Solver nie obchodzi tej reguły po cichu — diagnostyka/naprawa może zaproponować jej złagodzenie.

## Weryfikacja
- 13/13 testów jednostkowych: PASS,
- smoke backendu na 8092: PASS,
- test po wdrożeniu na 8091: PASS,
- headless Chromium: PASS, 0 page errors,
- cała szkoła: 354/354 aktywnych pozycji obsadzonych w bieżącym przebiegu,
- autostart: DEMO-Dyzury.cmd -> v5.7,
- rollback: katalog v5.6 + kopia autostartu .pre-v5.7.bak.
