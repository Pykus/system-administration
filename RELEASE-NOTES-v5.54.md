# RELEASE NOTES v5.54 — widoczne wyjątki i statystyki

- W grupie „Plan dyżurów” dodano trzeci przycisk „Statystyki” obok „Korytarz 1–3” i „Cała szkoła”.
- Statystyki są teraz dostępne bez rozwijania sekcji technicznej i domyślnie sortują nauczycieli malejąco po liczbie minut dyżuru.
- Tabela pokazuje w jednym miejscu: liczbę lekcji, dyżury 1–3, dyżury całej szkoły, sumę dyżurów, minuty, minuty dyżuru na lekcję, długie przerwy, oczekiwanie i rozkład Pn–Pt.
- Dodano szybki pasek obciążenia dla każdego nauczyciela oraz KPI z liczbą nauczycieli z dyżurem i bez dyżuru.
- Statystyki korzystają wyłącznie z zapisanego planu, a nie z roboczego szkicu Generatora.

- Nad planem 1–3, planem całej szkoły i statystykami pojawia się stały komunikat, jeśli preflight musiał zmienić niewykonalną regułę „Musi być” na „Zalecane 5 — Najwyższa”.
- Komunikat pokazuje nazwę reguły, przyczynę, minimalną liczbę koniecznych wyjątków i problematyczne sloty.
- Banner jest wyświetlany tylko wtedy, gdy dana automatycznie złagodzona reguła nadal faktycznie ma stan soft / priorytet 5.
- Po preflight UI aktualizuje komunikat natychmiast, bez potrzeby ręcznego odświeżania.

Testy: 119/119 OK + Python compile + JS syntax + staging health v5.54. Proveniencja automatycznie złagodzonej reguły pozostaje widoczna przy kolejnych preflightach tak długo, jak reguła nadal ma stan Zalecane 5.