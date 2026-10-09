# RELEASE NOTES v5.57 — statystyki i wykresy na żywo

- Zakładka „Statystyki” domyślnie śledzi najlepszy aktualny szkic Generatora zamiast czekać na ręczne zatwierdzenie planu.
- Źródło danych przełącza się automatycznie przy każdym nowym najlepszym szkicu; wykorzystuje istniejący polling Generatora co ok. 0,9 s.
- Jeśli solver jeszcze nie ma pełnego szkicu, statystyki pokazują zapisany plan i jasno informują, że czekają na pierwszy pełny wariant.
- Jeśli bieżące wyszukiwanie zostało anulowane, zakończyło się błędem albo jest nieaktualne po ręcznej zmianie danych, statystyki wracają do planu zapisanego.
- Dodano przełącznik „automatycznie śledź najlepszy szkic solvera”, pozwalający w każdej chwili wrócić do wyłącznie zapisanego planu produkcyjnego.

- Tabela, KPI, paski obciążenia i nowe wykresy korzystają z jednego wspólnego źródła danych.
- Dodano dwa automatycznie odświeżane wykresy: top 15 według minut dyżurów oraz top 15 według liczby dyżurów.
- Wykresy i tabela reagują na ten sam obiekt repairJob, więc zmieniają się bez ręcznego odświeżania strony.

- Zaktualizowano regresję v5.54: wcześniejszy test wymuszający wyłącznie zapisany plan został zastąpiony testem źródła live z bezpiecznym fallbackiem.
- Dodano 8 testów v5.57. Pełny zestaw: 137/137 testów OK, Python compile OK, JS syntax OK, staging health/validation OK.