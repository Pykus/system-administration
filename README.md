# v5.53 — preflight wykonalności przed CP-SAT

Najważniejsza reguła: wymagana obsada nie jest zmniejszana dlatego, że constraint utrudnia rozwiązanie. Obsada może zejść automatycznie do 0 tylko wtedy, gdy plan lekcji potwierdza brak dalszych lekcji w danej strefie. Jeżeli twarda reguła komfortu jest matematycznie niewykonalna przy pełnej obsadzie, preflight zmienia ją na „Zalecane 5 — Najwyższa”, pokazuje minimalną liczbę koniecznych wyjątków i dopiero potem uruchamia solver. Reguły systemowe, ręczne blokady i zakaz dyżuru w dniu bez lekcji nie są automatycznie luzowane.

# DEMO Dyżury v5.6 – OR-Tools

Aplikacja do układania dyżurów nauczycieli DEMO. FastAPI obsługuje API, Vue 3 interfejs, a wszystkie aktywne obliczenia przydziałów wykonuje Google OR-Tools CP-SAT.

## v5.6
- Zwężono stałe kolumny Godzina/Slot i zachowano stronicowanie po 12 nauczycieli.
- Kolejność zasad „Zalecane” jest trwała i służy tylko jako rozstrzygnięcie pomocnicze przy tym samym priorytecie; „Musi być” obowiązują równocześnie.
- Wyłączone zasady są wyszarzone; opisy używają wyłącznie „Musi być / Zalecane”.
- Warianty pełnej obsady pokazują dokładne dodane/usunięte dyżury nauczycieli i informację o oczekiwaniu.
- Dodano trwały rejestr nauczycieli z kategoriami ogólny / 1–3 / WF i automatyczne dopisywanie nowych osób z importu PDF.
- Dodano ograniczony panel nauczyciela /teacher z indywidualnym tokenem, własnym planem i własnymi preferencjami.
- Reguły / zasady przydziału przeniesiono pod Planowanie zaawansowane; Statystyki pod Plany nauczycieli.
- Przycisk publikacji planu przemianowano na punkt odniesienia dla zastępstw i wyjaśniono jego działanie.
- Strefy przejścia mają opisaną skalę 1–10.

## v5.5
- Naprawiono błąd HTTP 500 po zapisaniu pustego seeda; seed jest teraz wewnętrzny i automatycznie normalizowany.
- Diagnostyka proponuje wyłącznie warianty dające 100% obsady.
- Najpierw próbuje przeorganizować plan 1–3 i plan całej szkoły bez luzowania constraintów; dopiero później rozważa zmianę „Musi być” na „Zalecane”.
- Wariant pokazuje liczbę zmienionych stanowisk oraz imienną listę nauczycieli z dodanymi/usuniętymi dyżurami.
- „Unikaj dodatkowego oczekiwania” ma wysoki koszt poluzowania i jest rozważane później niż mniej obciążające zmiany.
- Nauczyciele ogólni dla 1–3 są najpierw dobierani spośród osób uczących klas 1–3 lub mających zajęcia w salach korytarza 1–3.
- Szerokie tabele mają strony po 12 nauczycieli; listy nauczycieli są alfabetyczne.
- Szczegóły techniczne solvera są schowane w rozwijanej sekcji.

## Najważniejsze funkcje
- Constrainty użytkownika: „Musi być” albo „Zalecane”.
- Priorytety preferencji 1–5: Drobna, Niska, Normalna, Wysoka, Najwyższa.
- Drag & drop kolejności reguł; przy tym samym priorytecie wyższa reguła ma pierwszeństwo.
- Stałe reguły systemowe: brak kolizji z lekcją, brak dwóch miejsc jednocześnie i respektowanie ręcznych blokad.
- Oczekiwanie jest sterowane wyłącznie constraintem „Unikaj dodatkowego oczekiwania”.
- Zachowanie obecnego planu jest sterowane wyłącznie constraintem „Zachowuj istniejący plan”.
- Długie przerwy: maks. dziennie 0–2 (domyślnie 1), tygodniowo 0–10 (domyślnie 3).
- Każdy dzień ma dwie 20-minutowe długie przerwy.
- Krótki dyżur po ostatniej lekcji jest domyślnie dopuszczalny; długa przerwa po ostatniej lekcji jest domyślnie silnie odradzana.
- Zakładka „Plany nauczycieli” łączy lekcje, dyżury i podsumowania dla każdej osoby.
- Diagnostyka pokazuje status backendu/CP-SAT, braki, legalnych kandydatów i powody odrzucenia.
- Walidacja jest osobną kartą w Diagnostyce i zgłasza sprzeczne lub błędne ustawienia.
- Czerwony badge przy Diagnostyce pokazuje łączną liczbę problemów solvera i walidacji.
- „Przelicz wszystko” zapisuje ustawienia, liczy oba zakresy i odświeża wszystkie liczniki/tabele.
- Planowanie zaawansowane obejmuje preferencje w siatce, współczynnik obciążenia, strefy, blokady przydziałów, nieobecności i tryb naprawczy Minimal Perturbation.
- v5.4: zapisane nieobecności są respektowane również przez zwykłe przeliczenie, nawet gdy żądanie solve nie powtarza listy `absent_teachers`.
- Obsługiwane są warianty A/B/C, tryb deterministyczny i publikacja planu operacyjnego.

## Uruchomienie
1. `python -m pip install -r requirements.txt`
2. `python -m uvicorn app:app --host 0.0.0.0 --port 8090`

Na DEMO-AI-NODE00 użyj `start_service.cmd`.

## Testy
Uruchom `python run_local_test_suite.py`.

Pakiet obejmuje regresję constraintów v5.1, funkcje v5.2, planowanie zaawansowane v5.3 oraz testy regresyjne v5.4 i v5.5. Test wdrożeniowy uruchamia aplikację na porcie testowym i sprawdza oba solvery przez HTTP.

## Dokumentacja
- `docs/ARCHITECTURE.md` – model OR-Tools i przepływ danych.
- `docs/USER_GUIDE.md` – obsługa aplikacji.
- `docs/CHANGELOG.md` – historia zmian i synchronizacji.


## Mapa obłożenia sal — v5.60.1
Widok /map pokazuje wykorzystanie sal na podstawie planu lekcji. Nie pokazuje komputerów ani inwentaryzacji IT. Kolor sali jest heat mapą liczby zajętych unikalnych slotów w tygodniu (maks. 45), a kliknięcie otwiera tygodniowy plan sali z klasą, przedmiotem, nauczycielem i wolnymi okienkami.

## v5.60.2 — wygaszanie strefy 1–3
Nieaktywnego slotu 1–3 nie można ponownie utworzyć przez obsadę ręczną ani indywidualny require_slot. Plan lekcji jest nadrzędny.

## v5.77 — WF dopiero jako awaryjny fallback

Automatyczne planowanie nie traktuje już nauczycieli WF jako zwykłej puli szkoły. Fazy podstawowe pracują bez WF; dopiero osobna faza awaryjna może ich włączyć. Kolejność krytycznych fallbacków to: WF → długa przerwa po ostatniej lekcji → dodatkowe oczekiwanie. Ręczne stałe przydziały WF pozostają nienaruszalne.

Po odblokowaniu WF CP-SAT minimalizuje liczbę ich przydziałów w obu zakresach, a live-gate nie przyjmuje szkicu z WF bez udowodnionego minimum. Fairness i preferencje grupowe nie mają prawa zwiększyć użycia WF.

## v5.77 canonical effective-plan contract

All plan-bearing screens use one backend effective-plan snapshot and one source_id.
A plan is complete only when every currently required position has a non-empty teacher
and the snapshot has no same-teacher/same-slot collision across scopes. Array length is
never accepted as evidence of coverage.

Explicit source kinds are live_verified, saved_verified, reference_verified and
invalid_saved. A reference plan is always labeled as a reference and is revalidated
against current staffing requirements before it can be displayed.


## v5.78 — preferencje nauczyciel × miejsce

Solver używa jednej macierzy preferencji dla wszystkich aktywnych nauczycieli i wszystkich konkretnych miejsc dyżuru. Dostępne wartości to 0 / 0,25 / 0,50 / 0,75 / 1,00. Dawne grupy 1–3 / ogólny / WF są tylko etykietami startowymi, nie pulami kandydatów. Zero jest kosztownym fallbackiem, nie zakazem.

Konfiguracja miejsc jest skupiona w zakładce **Miejsca dyżurów**. Systemowe punkty **Sala gimnastyczna A** i **Sala gimnastyczna B** są przeznaczone wyłącznie dla WF i aktywują się z planu zajęć sportowych. Więcej: `RELEASE-NOTES-v5.78.md` i `docs/CONSTRAINT-ARCHITECTURE.md`.
