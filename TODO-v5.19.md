# TODO v5.19

Status: backlog — NIE WDRAŻAĆ jeszcze.

## Domyślne parametry i szybkie znajdowanie rozwiązania
- [ ] Przy zwykłym „Przelicz” wykonywać szybki preflight wykonalności na aktualnych parametrach domyślnych, a nie zostawiać tej inteligencji wyłącznie diagnostyce/generatorowi naprawczemu.
- [ ] Jeśli parametr czysto pojemnościowy ewidentnie uniemożliwia pełne rozwiązanie, automatycznie podnieść jego wartość domyślną do najniższej wartości zapewniającej realną wykonalność.
- [ ] Przykład: gdy pula 1–3 i limit tygodniowy dają łączną pojemność mniejszą niż wymagana liczba dyżurów, zwiększyć najpierw limit liczby dyżurów / pojemność bez naruszania wygody.
- [ ] Zmiana automatyczna ma być minimalna, jawna w UI i raportowana użytkownikowi jako korekta parametru startowego.
- [ ] Nie zmieniać automatycznie reguł komfortu, jeśli problem da się rozwiązać parametrem neutralnym organizacyjnie.

## Kolejność automatycznych korekt — wygoda nauczycieli jest nadrzędna
- [ ] Najpierw korygować parametry neutralne dla wygody nauczycieli: pojemność, techniczne limity solvera, kolejność wyszukiwania, liczba workerów, timeouty, beam width, seedy, strategie restartu.
- [ ] Następnie minimalne zmiany strukturalne, które nie zwiększają oczekiwania ani nie wydłużają dnia pracy.
- [ ] Dopiero później rozważać zwiększenie indywidualnych limitów dyżurów, jeśli pozostaje to organizacyjnie akceptowalne.
- [ ] Parametry pogarszające komfort — dodatkowe oczekiwanie, przyjazd tylko na dyżur, dyżur przed pierwszą / po ostatniej lekcji, wydłużenie dnia, odległa strefa — zawsze jako ostatni etap.
- [ ] Warianty obniżające komfort muszą być wyraźnie oznaczone i nigdy nie mogą być preferowane ponad pełne rozwiązanie o wyższym komforcie.

## Profile ustawień
- [ ] Dodać profile parametrów domyślnych.
- [ ] Możliwość zapisania aktualnych parametrów jako nazwany profil.
- [ ] Możliwość wczytania profilu.
- [ ] Możliwość ustawienia wybranego profilu jako domyślnego.
- [ ] Profile powinny obejmować parametry solvera i reguły/limity, ale nie nadpisywać samego planu, ręcznych przydziałów ani danych nauczycieli bez wyraźnej decyzji użytkownika.
- [ ] Dodać co najmniej profil „Komfort nauczycieli” jako domyślny kierunek optymalizacji.
- [ ] Przy wczytywaniu profilu pokazać podsumowanie zmian przed zastosowaniem.

## Cel
- [ ] Zwykłe „Przelicz” ma możliwie szybko znajdować pełne rozwiązanie na sensownych parametrach startowych, bez konieczności przechodzenia do diagnostyki.
- [ ] Zachować zasadę: kompletność planu jest ważna, ale przy wyborze między pełnymi rozwiązaniami pierwszeństwo ma wygoda nauczycieli.
