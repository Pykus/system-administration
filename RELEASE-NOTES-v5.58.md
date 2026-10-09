# RELEASE NOTES v5.58 — jeden żywy plan na wszystkich ekranach

## Jedno źródło widoku
- Korytarz 1–3, Cała szkoła, Plany nauczycieli i Statystyki korzystają z tego samego najlepszego pełnego szkicu Generatora.
- Mapa miejsc, liczniki obsady, listy oczekiwania, paski i wykresy statystyczne również korzystają z tego samego źródła.
- Źródło przełącza się automatycznie przy pollingu Generatora (ok. 0,9 s).
- Do widoków live dopuszczany jest tylko wariant kompletny jednocześnie dla 1–3 i całej szkoły: missing=0 oraz filled=required w obu zakresach.
- Jeśli bieżący job jest stale/cancelled/failed albo nie ma jeszcze pełnego wariantu, wszystkie te ekrany wracają spójnie do zapisanego planu.

## Widoczność
- Nad głównymi ekranami planu jest stały pasek źródła: NA ŻYWO / zapisany plan.
- Live draft jest jawnie oznaczony jako niezapisany.
- Jeden globalny przełącznik pozwala wyłączyć live i wrócić do zapisanego planu na wszystkich ekranach jednocześnie.

## Edycja i eksport
- Ręczna edycja z widoku live wymaga jawnego przyjęcia widocznego szkicu jako bazy.
- Lokalna podmiana nauczyciela jest blokowana dla niezapisanego szkicu live.
- PDF, Excel, PNG/A4, JSON i zapis wariantu eksportują dokładnie to, co aktualnie pokazują ekrany administracyjne.
- Publiczny portal nauczyciela pozostaje oparty o plan zapisany/publikowany — niezapisany szkic nie jest publikowany nauczycielom.

## Regresja
- Zaktualizowano stare testy zakładające, że normalny ekran zawsze musi pokazywać wyłącznie zapisany plan.
- Dodano pełny audyt źródła danych dla 1–3, szkoły, planów nauczycieli, statystyk, mapy, KPI, oczekiwania, polling refresh i eksportów.
- Gate: 152/152 testów OK, Python compile OK, JavaScript syntax OK.
