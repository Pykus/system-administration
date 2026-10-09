# DEMO Dyżury v5.13 — 2026-09-19

- Odświeżenie strony odzyskuje aktywny Generator wariantów i podpina się do tego samego joba.
- Backend blokuje przypadkowe uruchomienie drugiego kosztownego wyszukiwania, gdy jedno już trwa.
- Przy 8 lokalnych zadaniach każdy lokalny CP-SAT używa 1 wątku, aby zachować responsywność API Node00.
- Zdalne workery są wykrywane dynamicznie także po rozpoczęciu etapu wyszukiwania.
- Zdalne workery pracują równolegle z lokalnymi; bieżący panel pokazuje zdalnie aktywne i ukończone zadania.
- Worker v1.1 (protokół 5.12) pozostaje zgodny z Planerem v5.13 — nie trzeba przebudowywać paczki workera.
- UI wyjaśnia stan, gdy broker działa, ale żaden worker jeszcze się nie zarejestrował.
- Test obciążeniowy: 8 lokalnych + 1 zdalny worker, API odpowiadało w ok. 95 ms; zdalny worker pobierał i kończył zadania.
