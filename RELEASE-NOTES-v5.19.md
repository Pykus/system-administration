# DEMO Dyżury v5.19

## Pełne rozwiązanie
- Generator nie traktuje końca małego beam-search jako końca pracy.
- Kandydaci do puli 1–3 nie są obcinani do pierwszych 18 osób.
- Po szybkich etapach działa etap gwarantowany i wyszukiwanie nie kończy się bez pełnego wariantu, chyba że użytkownik je zatrzyma.
- Zwykłe „Przelicz wszystko” czeka na co najmniej jeden pełny wariant, gdy plan bazowy ma braki.

## Wygoda nauczycieli
- Najpierw zmiany neutralne/techniczne i pojemnościowe, potem strukturalne, a pogorszenie komfortu jest na końcu.
- Automatyczna korekta może tylko podnieść matematycznie zbyt małe twarde limity pojemności.
- Nie luzuje automatycznie oczekiwania, dnia bez lekcji ani krawędzi dnia.

## Parametry i diagnostyka
- Przy zapisie parametrów podczas aktywnego szukania użytkownik jest pytany o zatrzymanie obliczeń.
- Następnie wybiera: tylko zapisz albo zapisz i przelicz od zera.
- Diagnostyka jest zerowana po zmianie parametrów.

## Profile
- Zapisywanie, wczytywanie, ustawienie domyślnego i usuwanie profili ustawień.
- Profil nie zapisuje planu ani ręcznych przydziałów.
- Profil „Komfort nauczycieli” tworzony automatycznie.

## Worker farm
- NODE00 jest tylko workerem lokalnym, nie zdalnym.
- Worker v1.4 używa protokołu 5.15 zgodnego z brokerem.
- Stare workery docierają do brokera przez S13, ale nie rejestrują się z powodu starego protokołu.
