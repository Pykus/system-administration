# RELEASE NOTES v5.51 — widoczność nauczycieli w kalendarzu

- Pula kandydatów 1–3 pozostaje bez zmian i nadal może zawierać nauczycieli ogólnych/WF.
- Dolny kalendarz 1–3 pokazuje nauczycieli grupy 1–3 oraz nauczycieli spoza tej grupy tylko wtedy,
  gdy faktycznie mają co najmniej jeden przydzielony dyżur 1–3 w aktualnie wyświetlanym planie/szkicu.
- Samo dodanie nauczyciela ogólnego do puli 1–3 nie tworzy już jego kolumny w kalendarzu 1–3.
- Nauczyciel ogólny dodany awaryjnie do puli 1–3 pozostaje widoczny w kalendarzu całej szkoły.
- Podgląd roboczego wariantu Generatora również pokazuje nauczyciela spoza 1–3, jeśli wariant faktycznie przydzielił mu dyżur 1–3.
- Solver, pule kandydatów, przydziały i dane nie zostały zmienione.

TDD: 3 nowe testy v5.51.
Pełny gate przed wdrożeniem: 92/92 OK + Python compile + JS syntax.
