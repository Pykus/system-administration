# Planner dyżurów 5.43

- TDD gate: 29/29 OK.
- Warianty zachowują obsadę per stanowisko i pełniejszą konfigurację solvera.
- Wczytanie wariantu tworzy nową rewizję i unieważnia stary job.
- Lokalne podmiany i ich zwalnianie unieważniają job oparty o stary stan.
- Deployment zachował dane użytkownika; cztery krytyczne pliki danych mają identyczne SHA-256 względem 5.42.
- Checkpoint poprzedniego joba przetrwał restart i został odtworzony jako interrupted.
