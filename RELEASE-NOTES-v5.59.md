# RELEASE NOTES v5.59 — filtr skrajnie nierównych wariantów

## Co było źle
Reguła „Sprawiedliwy podział wg obciążenia dydaktycznego” była włączona jako ZALECANE, priorytet 5, ale szybkie pełne szkice były porządkowane przede wszystkim według oczekiwania i reguł brzegowych. W krótkim przebiegu CP-SAT mógł więc znaleźć pełny, lecz skrajnie nierówny plan i taki szkic trafiał wysoko do dalszej analizy.

## Zmiana
- Każdy pełny szkic dostaje profil równomierności liczony względem celu: liczba lekcji × ręczny współczynnik nauczyciela.
- Skrajnie nierówny szkic jest odrzucany natychmiast przed wejściem do podglądu live i przed LNS/dalszą optymalizacją.
- Bramka skrajności wykrywa m.in. bardzo duże łączne odchylenie, >3× celu z dużym nadmiarem oraz koncentrację >55% wszystkich dyżurów w top 10 osób.
- Warianty, które przejdą bramkę, są dodatkowo sortowane z równomiernością przed regułami brzegowymi, po bezwzględnym wymaganiu braku oczekiwania.
- Diagnostyka pokazuje liczbę pełnych szkiców odrzuconych za skrajną nierównomierność oraz metrykę odchylenia i maksymalnego przeciążenia dla zachowanych szkiców.
- Widok live jawnie odrzuca wariant oznaczony jako skrajnie nierównomierny.

## Kalibracja na rzeczywistych wariantach
- Dotychczasowy szkic z 37 dyżurami jednej osoby: odchylenie 118%, max 4.53× celu, top 10 = 64% wszystkich dyżurów — ODRZUCONY.
- Szkic z maksimum 17 dyżurów: odchylenie 51%, max 2.59× celu, top 10 = 31% — przechodzi bramkę i może być dalej poprawiany.

## Testy
- 159/159 testów OK.
- Python compile OK.
- JavaScript node --check OK.
