# DEMO Dyżury v5.12 — 2026-09-19

- Naprawiono fałszywe „brak rozwiązań”: status CP-SAT UNKNOWN nie jest już traktowany jak 0/354, tylko ponawiany i raportowany jako nierozstrzygnięty, jeśli nadal zabraknie czasu.
- Generator sprawdza oba kierunki przebudowy: 1–3 → szkoła oraz szkoła → 1–3; pierwszy pełny wynik kończy zbędne dalsze próby.
- Nauczyciele grupy 1–3 są bezwzględnie wykluczeni z dyżurów ogólnoszkolnych po stronie backendu, generatora, zapisu stanu i UI.
- Dodatkowe oczekiwanie pozostaje absolutnie ostatnim etapem generatora. Test regresyjny potwierdza, że poluzowanie avoid_wait daje na obecnych danych 95/95 i 354/354.
- Diagnostyka rozróżnia brak rozwiązania od nierozstrzygnięcia w limicie czasu i pokazuje liczbę nierozstrzygniętych prób.
- Zachowano minimalną obsadę całej szkoły, możliwość użycia nauczycieli ogólnych w 1–3, Minimal Perturbation i pełne odświeżanie po „Przelicz wszystko”.
- Regresja 9/po: obsada ustawiona na 1 tworzy dokładnie jedno stanowisko.
- Zdalny worker v1.1 używa tej samej polityki v5.12, obu kierunków oraz retry UNKNOWN.
- Farma: domyślnie 4 lokalne workery, broker 8093 OFF do jawnego włączenia.
