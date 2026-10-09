# v5.14 — 2026-09-19

- beam search + checkpointy wyników częściowych,
- głęboka weryfikacja 15–60 s,
- zachowanie pełnego rozwiązania bez ponownego solve,
- braki całej szkoły w UI,
- poprawna reguła 8093 dla 198.51.100.29.0/24,
- paczka worker v1.1-r2 z diagnostyką sieci.

# v5.12 — 2026-09-19

- naprawa UNKNOWN → fałszywe braki; retry i jawna diagnostyka nierozstrzygnięcia,
- dwukierunkowa przebudowa 1–3 ↔ szkoła,
- grupa 1–3 bezwzględnie wyłączona z dyżurów całej szkoły,
- oczekiwanie nadal wyłącznie w ostatnim etapie,
- test 9/po = 1 osoba = 1 stanowisko,
- worker v1.1 zgodny z plannerem 5.12,
- domyślnie 4 lokalne workery, broker zdalny OFF.

# v5.8 — 2026-09-19

- poprawiono semantykę „przed lekcją”: dotyczy wyłącznie przerwy przed pierwszą lekcją nauczyciela danego dnia,
- długie/dłuższe niż 5 min przerwy przed pierwszą i po ostatniej lekcji są stałą twardą polityką i nie są proponowane do poluzowania,
- 5-minutowe przerwy przed pierwszą i po ostatniej lekcji są osobnymi, opcjonalnymi constraintami,
- dodano automatyczną proporcjonalność dyżurów do liczby lekcji w tygodniowym planie,
- ręczna waga udziału i współczynnik z planu są pokazane osobno; przy obu aktywnych ręczna waga jest mnożnikiem korekcyjnym,
- ekran nauczyciela łączy lekcje i dyżury w jednej osi czasu z godzinami lekcji i przerw,
- widok zbiorczy zwiększono z 12 do 15 nauczycieli na stronę,
- doprecyzowano, że macierze obsady 1–3 i całej szkoły są ustawieniami wejściowymi solvera, a nie wynikami.
# v5.7 — 2026-09-19

- minimalna obsada całej szkoły: trwała macierz 0/1 dla miejsce × dzień × przerwa,
- lista miejsc dyżurów całej szkoły jest konfigurowalna; migracja zachowuje wszystkie miejsca z planu źródłowego i bieżących przydziałów,
- pula 1–3 odzyskała przycisk „+ nauczyciele ogólni”,
- warianty naprawcze są najpierw przeglądane, dopiero potem jawnie stosowane,
- dodano bezpieczny fallback kopiowania linków nauczycieli dla zwykłego HTTP,
- „Sloty lekcji” zmieniono na „Lekcji w planie”,
- pełne przeliczenie odświeża także rejestr nauczycieli, macierz obsady i listę miejsc,
- dodano regresję 9/po: przy obsadzie 1 i jednej regule „wymagaj nauczyciela” powstaje dokładnie jedno stanowisko,
- walidacja wykrywa nieaktywne miejsca wymaganych dyżurów i błędną macierz obsady szkoły.

# CHANGELOG

## 5.6 – 2026-09-19
- Uproszczono nawigację i język interfejsu.
- Dodano trwały teacher_registry.json oraz panel zarządzania nauczycielami.
- Import planów dodaje nowych nauczycieli i klasyfikuje ich do 1–3 / ogólnych / WF.
- Dodano osobny panel /teacher z tokenem i własnymi preferencjami.
- Rozszerzono diagnostykę wariantu o konkretne dodane/usunięte dyżury i oczekiwanie.
- Kolejność zasad jest automatycznie zapisywana; wyłączone zasady są szare.
- Reguły przeniesiono pod Planowanie zaawansowane, statystyki pod Plany nauczycieli.
- Wyjaśniono punkt odniesienia dla zastępstw i skalę stref 1–10.

## 5.5 – 2026-09-19
- Naprawiono HTTP 500 powodowane pustą wartością solver_seed.
- Seed ukryto przed zwykłym użytkownikiem; backend bezpiecznie używa wartości domyślnej.
- Automatyczne propozycje przeniesiono na górę Diagnostyki i pokazują wyłącznie warianty 100%.
- Dodano priorytet przeorganizowania planów bez luzowania constraintów oraz semantyczny koszt poluzowania reguł; dodatkowe oczekiwanie jest kosztowne.
- Dodano Minimal Perturbation do wyliczania wpływu wariantu i imienną listę zmian nauczycieli.
- Awaryjne włączenie nauczycieli ogólnych preferuje osoby powiązane z klasami/salami 1–3.
- Dodano stronicowanie szerokich planów po 12 nauczycieli i alfabetyczne sortowanie list.
- Uproszczono UI: diagnostyka techniczna i ustawienia solvera są rozwijane.

## 5.4 – 2026-09-18
- Wersja scalająca po wykryciu równoległej pracy kilku wątków ChatGPT nad tą samą aplikacją.
- Bazą została najnowsza v5.3; zachowano wszystkie funkcje v5.1–v5.3 i wymagania dotyczące OR-Tools.
- Poprawiono wskaźnik start_service.cmd na bieżący katalog v5.4.
- Zaktualizowano dokumentację architektury, README i testy wersji.
- Dodano test scalający v5.4 dla limitów długich przerw, wymaganych powierzchni UI, stałych reguł systemowych i ścieżki usługi.
- Naprawiono respektowanie zapisanych nieobecności przez zwykłe wywołania solvera; `absent_teachers` ze stanu jest domyślnie używane, jeśli nie podano listy w żądaniu.
- Przed wdrożeniem wykonywane jest porównanie SHA-256 plików bazowych v5.3, aby wykryć późniejsze równoległe zmiany.

## 5.3 – 2026-09-18
- Dodano planowanie zaawansowane: współczynniki obciążenia/pensum, siatkę preferencji i strefy lokalizacji.
- Dodano zamrażanie wybranych przydziałów oraz obsługę nieobecności.
- Tryb naprawczy używa Minimal Perturbation: najpierw minimalizuje braki, potem liczbę zmian względem planu odniesienia, a dopiero potem preferencje.
- Dodano tryb deterministyczny i seed solvera.
- Rozszerzono warianty i porównanie planów A/B/C.
- Dodano publikację snapshotu i planu operacyjnego.
- Rozszerzono walidację i diagnostykę o dane planowania zaawansowanego.

## 5.2 – 2026-09-18

- „Przelicz wszystko” najpierw zapisuje bieżące constrainty i stan roboczy, a dopiero potem uruchamia solver 1–3 i solver całej szkoły.
- Dodany widoczny stan przeliczania: spinner, etapy 1/5–5/5, komunikat końcowy i czas ostatniego pełnego przeliczenia.
- Po pełnym przeliczeniu odświeżane są: plany, statystyki, liczniki, diagnostyka, walidacja i źródłowa konfiguracja osi czasu.
- Macierze planu mają klucz odświeżania, aby Vue nie pozostawiało starych komórek po zmianie wyniku.
- Walidacja została przeniesiona do Diagnostyki i otrzymała opis użytkowy wyjaśniający, co dokładnie sprawdza.
- Diagnostyka potrafi automatycznie znaleźć minimalne poluzowanie konfigurowalnych reguł HARD do SOFT, które daje pełną obsadę; najpierw testuje pojedyncze zmiany, następnie najlepsze pary.
- Reguły stałe (kolizja z lekcją, dwa miejsca jednocześnie, ręczna blokada) nigdy nie są proponowane do poluzowania.
- Ujednolicono rozkład dzwonków dla wszystkich pięciu dni. Każdy dzień ma identyczną oś czasu i dokładnie dwie 20-minutowe długie przerwy.
- Poprawiono czytelność fontu: Segoe UI, większe rozmiary tabel i nagłówków oraz lepsze wygładzanie.
- Dodano testy v5.2 dla identycznego rozkładu dzwonków, dwóch długich przerw dziennie, zintegrowanej Diagnostyki/Walidacji i widocznego odświeżania GUI.

## 5.1 – 2026-09-18

- Przebudowa solvera na Google OR-Tools CP-SAT.
- Dwuetapowy cel CP-SAT: najpierw minimalizacja braków, następnie optymalizacja preferencji przy tej samej liczbie braków; usuwa potrzebę wielkich kar liczbowych i ryzyko przepełnienia modelu.
- Zachowanie dotychczasowych constraintów globalnych i indywidualnych.
- Naprawiona semantyka „tylko przed lekcją” i „tylko po lekcji”.
- Dodane testy dla przypadku przed lekcją, po lekcji i pomiędzy dwiema lekcjami.
- Nowy interfejs „Musi być” / „Zalecane”.
- Priorytety 1–5 z przyjaznymi nazwami i oznaczeniami kolorystycznymi.
- Drag & drop kolejności constraintów.
- Usunięta abstrakcyjna kolumna „Wartość”; ustawienia liczbowe mają własne etykiety.
- Usunięty checkbox awaryjnego oczekiwania.
- Usunięty checkbox zachowania obecnego planu.
- Dodany constraint maksymalnej liczby długich przerw dziennie: domyślnie 1, zakres 0–2.
- Dodany constraint maksymalnej liczby długich przerw tygodniowo: domyślnie 3, zakres 0–10.
- Limity długich przerw liczone łącznie z obu zakresów dyżurów.
- Dodana zakładka „Plany nauczycieli”.
- Dodana zakładka „Diagnostyka” z analizą odrzuceń i nieobsadzonych pozycji.
- Dodany endpoint /api/health.
- Dodana zakładka i endpoint „Walidacja”.
- Walidacja odświeża się przy wejściu na zakładkę i waliduje także bieżące, jeszcze niezapisane ustawienia constraintów.
- Dodany czerwony licznik problemów przy zakładkach diagnostycznych.
- Reguły fizycznie oczywiste (kolizja z lekcją, dwa miejsca jednocześnie, ręczna blokada) przeniesione do stałych reguł systemowych bez możliwości wyłączenia.
- Globalny „zakaz dyżuru tylko po lekcji” zastąpiony dwoma niezależnymi constraintami: krótka przerwa po ostatniej lekcji oraz długa przerwa po ostatniej lekcji.
- Krótka przerwa po ostatniej lekcji jest domyślnie dopuszczona; unikanie długiej przerwy po ostatniej lekcji jest domyślnie regułą SOFT o wysokiej ważności.
- Poprawiony kontrast interfejsu: ciemny tekst na jasnych tłach nagłówków i aktywnych elementów.
- Migracja starych wag priorytetów do skali 1–5.
- Rozszerzony pakiet testów i raport TEST_REPORT_v5.1.json.

## 4.6

- HARD/SOFT dla constraintów.
- Testy lokalne i wdrożeniowe.
- Regresja zakazu oczekiwania.


## 5.53 — 2026-09-23
- Preflight stał się bramką wykonalności przed CP-SAT: nie uruchamia kosztownego wyszukiwania, jeśli proste dopasowanie już dowodzi braku rozwiązania.
- Usunięto propozycje redukcji wymaganej obsady (m13/ms) jako reakcję na brak kandydatów. Zero obsady pozostaje wyłącznie skutkiem nieaktywnej strefy z planu lekcji.
- Niewykonalne twarde reguły komfortu są automatycznie zapisywane jako soft, priorytet 5, z raportem minimalnych wyjątków i dotkniętych slotów.
- Preflight wybiera najmniej kosztowy zestaw reguł brzegowych przez pełny przegląd małego zbioru kombinacji; dodatkowe oczekiwanie ma najwyższy koszt i pozostaje ostatnim wyborem.
- Dodano obsługę indywidualnych twardych reguł no_before_first_lesson / no_after_last_lesson: wyjątek dotyczy tylko konkretnego nauczyciela.
- Dodano dowód dla koniecznych kolejnych dyżurów przez wspólne dopasowanie dwóch sąsiednich przerw.
- Limity pojemności, których wartość jest zbyt niska z samej arytmetyki obsady, są łagodzone do „Zalecane 5” bez zmiany wpisanej wartości.
- UI jednoznacznie pokazuje automatyczne złagodzenia i nie proponuje już redukcji obsady jako naprawy constraintu.

## 5.54 — 2026-09-23
- Dodano główną zakładkę Statystyki jako trzeci widok planu.
- Rozszerzono statystyki o liczbę lekcji i minuty dyżuru na lekcję oraz wizualny pasek obciążenia.
- Statystyki bazują na zapisanym planie, nie na szkicu roboczym.
- Dodano widoczny banner aktywnych automatycznie złagodzonych constraintów nad planami i statystykami.
- Banner zawiera minimalne wyjątki i sloty z dowodu preflightu oraz znika, jeśli reguła przestaje być aktywnym soft priority 5.
- Preflight aktualizuje dane bannera w UI natychmiast po automatycznym złagodzeniu.
- TDD: 10 nowych testów v5.54; pełny gate 119/119 OK.
- Proveniencja automatycznych wyjątków jest trwała: kolejny preflight nie usuwa bannera, jeśli reguła nadal pozostaje soft priority 5; wpis znika po ręcznej zmianie charakteru/priorytetu reguły.
## 5.55 — 2026-09-23
- Rozdzielono w szkicach roboczych: udowodnione minimum, kandydatów preflightu i faktyczne naruszenia obecnego szkicu.
- Dodano per-rule proof dla after_last_long / before_first_long: porównanie matching HARD vs SOFT przy niezmienionych pozostałych regułach.
- Raportuje co najmniej ilu różnych nauczycieli jest koniecznych jako wyjątek oraz minimalną liczbę przydziałów wyjątkowych w tygodniu.
- Kandydaci są wyznaczani jako nauczyciele, którzy stają się legalni dokładnie po poluzowaniu analizowanej reguły.
- Metryki szkicu pokazują liczbę unikalnych długich przerw i rozkład przydziałów po slotach.
- Usunięto mylące opisy „przypadek/przypadki” dla listy nauczycieli; lista jest opisana jako faktyczne przydziały konkretnego szkicu.
- TDD: 5 nowych testów v5.55; pełny gate 124/124 OK.
## 5.56 — 2026-09-23
- Ujednolicono nazewnictwo reguł przed/później względem lekcji: „przerwa >5 min”, zamiast mylącego „długa przerwa”.
- Dodano jawne wyjaśnienie, że kategoria >5 min obejmuje również przerwy 10-minutowe.
- Zachowano osobny próg 15 min dla limitów prawdziwych długich przerw.
- Zaktualizowano etykiety kompromisów i kolejność przywracania reguł.
- TDD: 5 dodatkowych testów semantyki progów; pełny gate 129/129 OK.

## 5.57 — 2026-09-23
- Statystyki domyślnie śledzą najlepszy aktualny szkic Generatora zamiast wyłącznie zapisanego planu.
- Tabela, KPI, paski obciążenia i wykresy używają wspólnego źródła live.
- Źródło live aktualizuje się wraz z istniejącym pollingiem Generatora co ok. 0,9 s.
- Dodano jawny status źródła: NA ŻYWO / szkic wstrzymany / ostatni wynik / zapisany plan.
- Dodano przełącznik wyłączenia śledzenia solvera i powrotu do planu produkcyjnego.
- Dodano dwa wykresy top 15: według minut dyżurów i według liczby dyżurów.
- Nieaktualne, anulowane lub błędne wyszukiwanie nie może nadpisywać statystyk planu zapisanego.
- Zaktualizowano test v5.54, który wcześniej wymuszał statystyki wyłącznie z planu zapisanego.
- TDD: 8 nowych testów v5.57; pełny gate 137/137 OK.
## 5.58 — 2026-09-23
- Wprowadzono wspólne `livePlanVariant` jako źródło najlepszego pełnego szkicu dla wszystkich administracyjnych ekranów planu.
- Korytarz 1–3, Cała szkoła, Plany nauczycieli, Statystyki, mapa miejsc, KPI i listy oczekiwania odświeżają się z tym samym wariantem.
- Live wymaga pełnej obsady obu zakresów; szkic częściowy nie może zastąpić planu na ekranach głównych.
- Polling Generatora co ok. 0,9 s aktualizuje `refreshEpoch` także wtedy, gdy zmienia się najlepszy pełny szkic, niezależnie od diagnostycznego podglądu wariantów.
- Usunięto osobne przełączniki live z ekranów; jest jeden globalny przełącznik źródła.
- Plany nauczycieli i ich statystyki zostały przepięte z surowych `rows13/schoolCurrent` na wspólne źródło wyświetlane.
- Eksport PDF, Excel, PNG/A4, JSON i zapis wariantu korzystają z planu aktualnie widocznego.
- Lokalna korekta nie może działać na niezapisanym szkicu; ręczna edycja wymaga jawnego przyjęcia szkicu jako bazy.
- Testy regresyjne: 152/152 OK; dodano `test_v558_live_all_screens.py` (w tym audyt zakazujący surowych `rows13/schoolCurrent/sum*/waits*` w czterech ekranach planu) i zaktualizowano starsze założenia v5.52/v5.54/v5.57.

## 5.59 — 2026-09-23
- Naprawiono priorytetyzację pełnych szkiców przy aktywnej regule `lesson_load_fairness`.
- Dodano profil równomierności względem celu wynikającego z liczby lekcji × ręczny współczynnik.
- Skrajnie nierówne pełne szkice są odrzucane przed podglądem live i przed dalszą optymalizacją.
- Kryteria skrajności: znormalizowane odchylenie >0.75, albo >3× celu z nadmiarem >=8 dyżurów, albo top 10 osób >55% wszystkich dyżurów.
- Ranking akceptowalnych szkiców uwzględnia równomierność przed regułami brzegowymi.
- UI pokazuje liczbę odrzuconych nierównych szkiców i metryki równomierności zachowanych wariantów.
- Testy regresyjne: 159/159 OK.

## 5.60 — 2026-09-23
- Dodano HUMAN_REALISM_HARDENED_V560 dla limitów kolejnych/dziennych/tygodniowych/długich dyżurów.
- Limity człowieka nie są automatycznie luzowane przez preflight ani Generator.
- Jednorazowa migracja zmienia max_consecutive_duties 2 → 1; późniejsze ręczne zmiany są zachowywane.
- Szybkie pełne szkice zawsze zachowują limity człowieka.
- Dodano human_guardrail_profile oraz odrzucanie szkiców naruszających twarde limity przed live/LNS.
- UI pokazuje filtr realnego planu oraz max tygodniowo/dziennie/najdłuższy ciąg dla każdego szkicu.
- Test na realnej kopii: pełne 70/70 + 385/385, najdłuższy ciąg 1, max tydzień 9, max dzień 4.
- Regresja: 167/167 OK.

## 5.60.1 — 2026-09-24
- Przebudowano /map z mapy komputerów na heat mapę wykorzystania sal.
- /api/map/lessons agreguje bieżący plan według sali, dnia i godziny; współprowadzenie nie zawyża obłożenia.
- Modal sali pokazuje klasy, przedmioty, nauczycieli oraz wolne sloty Pn–Pt / 1–9.
- Czerwone nasycenie sal odpowiada udziałowi zajętych slotów w 45 możliwych slotach tygodniowych.
- Usunięto z mapy wizualizację i listy komputerów.
- Dodano testy regresyjne mapy oraz forward-port do roboczej gałęzi v5.61.

## 5.60.2 — 2026-09-24
- Naprawiono możliwość pozostawienia/wstrzyknięcia indywidualnego hard require_slot dla wygaszonego slotu korytarza 1–3.
- Wygaszona strefa 1–3 ma zawsze obsadę 0; ręczne API nie może jej ponownie aktywować.
- Stan jest sanitowany przy odczycie i zapisie: usuwane są 1–3 require_slot oraz zapisane przydziały w slotach, które według planu już nie istnieją.
- Solver ma dodatkowy filtr obronny i ignoruje require_slot 1–3 dla nieaktywnego slotu.
- Źródłem incydentu były stare skrypty testowe uderzające w port produkcyjny 8091 i odtwarzające błędną ścieżkę v5.1.

## 5.62 — 2026-09-24
- prefer_home_group podniesione jednorazowo z soft priority 3 do soft priority 5.
- Po pełnej obsadzie osobny etap CP-SAT minimalizuje liczbę przydziałów spoza właściwej grupy.
- Drugi etap leksykograficzny dla 1–3 minimalizuje WF wśród koniecznych fallbacków: 1–3 → ogólni → WF.
- Szybkie/live szkice nie mogą już automatycznie poluzować prefer_home_group.
- Ranking pełnych szkiców rozróżnia fallback ogólny i WF; przy tej samej liczbie outsiderów preferuje mniej WF.
- Dodano metryki home_group_foreign_13_general i home_group_foreign_13_wf.
- Dodano rejestr architektury wszystkich 23 constraintów i test warstwy implementacyjnej.
- Real-state perf gate: dwa pełne przebiegi 80/80 + 385/385, 78/2/0 (1–3/ogólni/WF), 19.436–21.204 s.
- Regresja: 186/186 OK.

## 5.77 — 2026-09-25
- WF usunięto z automatycznych pul faz 1–3, nawet jeśli figurują w zapisanej konfiguracji.
- Ręczne stałe przydziały administratora dla WF pozostają legalnym wyjątkiem.
- Dodano osobną fazę 4 „awaryjny fallback WF”; `after_last_long` przesunięto na fazę 5, a `avoid_wait` na fazę 6.
- Preflight nie może już przemycić WF jako „oczywistej” naprawy etapu 1.
- Szerokie anchory i szybkie/live szkice nie używają WF przed fazą 4.
- CP-SAT minimalizuje liczbę przydziałów WF zarówno dla 1–3, jak i całej szkoły.
- Live-gate wymaga odblokowania fazy WF oraz statusu OPTIMAL dla minimum WF.
- Dodano metryki `wf_assignments_13`, `wf_assignments_school`, `wf_assignments_total`.
- Ranking pełnych szkiców utrwala kolejność: brak oczekiwania → brak `after_last_long` → minimum WF → pozostałe cele jakościowe.
- Dodano regresję v5.77, w tym realny test CP-SAT całej szkoły: nauczyciel ogólny wygrywa z WF przy równoważnej dostępności.


## 5.78
- zastąpiono pule nauczycieli macierzą preferencji nauczyciel × konkretne miejsce,
- połączono konfigurację miejsc w jeden widok,
- dodano systemowe Sala gimnastyczna A/B, WF-only i auto-obsadę z planu,
- dodano leksykograficzny koszt preferencji miejsca do CP-SAT,
- usunięto generowanie tokenów rozszerzania pul przez nowy Generator,
- dodano dekompozycję solve szkoły: gym → pozostałe miejsca,
- dodano matrix/zone map do podpisu Solvera, fingerprintu learningu i wariantów,
- rozszerzono regresję o testy macierzy, A/B, WF-only i spójność UI/backend.

## 5.79 — 2026-09-26
- Wprowadzono twardy kontrakt „single plan truth”: jedynym źródłem stanu planu dla GUI jest `/api/effective-plan`.
- `source.verified=true` oznacza, że ten sam pełny plan jest rysowany na wszystkich ekranach; `verified=false` oznacza brak planu na wszystkich ekranach.
- Frontend nie wylicza już własnego stanu „mam plan / czekam” z `recalculating` ani `repairJob`.
- Niezweryfikowany zapisany/częściowy stan nie jest zwracany jako dane planu: `result_13=[]`, `result_school=[]`.
- Status „LICZENIE” zależy od backendowego statusu zadania; po błędzie/zakończeniu bez pełnego planu UI pokazuje „Brak zweryfikowanego pełnego planu”.
- Komunikat o poprawnym przeliczeniu może pojawić się wyłącznie przy `effectivePlan.source.verified=true`.
- Portal nauczyciela również ukrywa stare dyżury, gdy kanoniczne źródło nie jest zweryfikowane.
- Banner wyjątków preflightu jest pokazywany dopiero po preflighcie wykonanym w bieżącej sesji UI.
- Naprawiono regresję UTF-8 w `state.json`; rozszerzono test integralności o typowe sekwencje mojibake.
