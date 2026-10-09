# Instrukcja użytkownika – DEMO Dyżury v5.1

## Reguły / constrainty

Każda reguła ma przełącznik aktywności oraz charakter:
- „Musi być” – solver nie może naruszyć reguły.
- „Zalecane” – solver może ją naruszyć, jeśli jest to potrzebne do lepszego lub pełnego planu.

Dla „Zalecane” wybiera się ważność 1–5. Nie trzeba podawać żadnych technicznych wag liczbowych.

Wiersze reguł globalnych można przeciągać. Przy tym samym poziomie ważności reguła znajdująca się wyżej ma pierwszeństwo.

Nad tabelą znajduje się lista reguł stałych, których nie można wyłączyć: brak dyżuru podczas prowadzenia lekcji, brak dwóch miejsc jednocześnie oraz bezwzględne respektowanie ręcznych blokad.

Dwa osobne constrainty sterują dyżurem bezpośrednio po ostatniej lekcji nauczyciela:
- „Dyżur po ostatniej lekcji – krótka przerwa” – domyślnie wyłączony, więc krótki dyżur jest dopuszczalny;
- „Unikaj dyżuru po ostatniej lekcji – długa przerwa” – domyślnie ZALECANE z wysoką ważnością; można przełączyć na MUSI BYĆ.

## Długie przerwy

W szkole są dwie długie przerwy dziennie, dlatego:
- „Maks. długich przerw dziennie” przyjmuje wartości 0–2,
- „Maks. długich przerw tygodniowo” przyjmuje wartości 0–10.

Domyślne ustawienia to odpowiednio 1 i 3.

## Oczekiwanie i zachowanie planu

Nie ma już dodatkowych checkboxów na ekranach solvera.

Oczekiwanie jest kontrolowane wyłącznie regułą „Unikaj dodatkowego oczekiwania”.
Zachowanie obecnych przydziałów szkoły jest kontrolowane wyłącznie regułą „Zachowuj istniejący plan szkoły”.

Dzięki temu każde zachowanie solvera ma jedno źródło konfiguracji.

## Plany nauczycieli

Zakładka „Plany nauczycieli” pokazuje osobną kartę dla każdej osoby:
- tabelę planu lekcji,
- tabelę dyżurów 1–3 i ogólnoszkolnych,
- liczbę dyżurów,
- liczbę minut,
- liczbę długich przerw,
- liczbę przypadków oczekiwania.

Wyszukiwarka filtruje nauczycieli po nazwisku lub imieniu.

## Diagnostyka

Po przeliczeniu planu zakładka „Diagnostyka” pokazuje:
- czy backend odpowiada,
- wersję aplikacji i OR-Tools,
- status CP-SAT,
- czas rozwiązania,
- nieobsadzone pozycje,
- liczbę legalnych kandydatów,
- powody odrzucania kandydatów.

Czerwony licznik przy zakładce oznacza łączną liczbę problemów solvera i walidacji.

W tej samej zakładce znajduje się sekcja „Walidacja konfiguracji”. Sprawdza ona spójność danych i reguł, a nie jakość wygenerowanego planu: wykrywa m.in. sprzeczne reguły HARD, wymagane dyżury kolidujące z lekcjami, błędne limity i odwołania do nieistniejących nauczycieli lub slotów.

Sekcja „Automatyczna propozycja dojścia do pełnej obsady” testuje minimalne poluzowanie konfigurowalnych reguł HARD do SOFT. Reguły fizycznie niemożliwe do naruszenia nie są brane pod uwagę. Wariant można zastosować jednym przyciskiem, co uruchamia pełne przeliczenie.

## Walidacja (wewnątrz Diagnostyki)

Sekcja Walidacja służy do wykrywania błędów konfiguracji przed solverem.

Przykładowe konflikty:
- nauczyciel jednocześnie „musi być” i jest twardo niedostępny,
- wymagany dyżur koliduje z lekcją,
- zbyt wiele wymaganych osób na jednym dyżurze,
- limit długich przerw jest poza zakresem,
- reguła wskazuje nieistniejącego nauczyciela.

Przy problemach zakładka pokazuje czerwony licznik i jest wizualnie wyróżniona. Dane walidacji są pobierane ponownie przy wejściu na zakładkę. Walidacja korzysta także z aktualnych ustawień widocznych w GUI, nawet jeżeli nie zostały jeszcze zapisane.

## Zalecany sposób pracy

1. Ustaw reguły „Musi być”.
2. Ustaw ważność preferencji „Zalecane”.
3. Uruchom Walidację.
4. Usuń ewentualne błędy.
5. Przelicz 1–3.
6. Sprawdź Diagnostykę.
7. Przelicz całą szkołę.
8. Sprawdź Plany nauczycieli i Statystyki.
9. Zapisz wariant.



## Planowanie zaawansowane (v5.3+)

Zakładka „Planowanie zaawansowane” pozwala ustawić:
- współczynnik obciążenia/pensum nauczyciela,
- preferowane i niepożądane sloty,
- strefy lokalizacji,
- zamrożone przydziały,
- nieobecności,
- seed i tryb deterministyczny solvera.

Tryb naprawczy używa zasady Minimal Perturbation: najpierw zachowuje możliwie największą część planu odniesienia, a zmienia tylko to, co jest potrzebne do usunięcia braków lub obsługi nieobecności.

## Synchronizacja równoległych zmian

Wersja v5.4 została przygotowana jako gałąź scalająca po wykryciu równoległej pracy kilku wątków ChatGPT. Przed przełączeniem produkcji należy porównać sumy SHA-256 plików bazowych v5.3. Jeśli v5.3 zmieniła się po utworzeniu v5.4, różnice należy najpierw przenieść do v5.4 i ponownie uruchomić testy.



## v5.6 – najważniejsze zmiany
- „Reguły / zasady przydziału” znajdują się na początku Planowania zaawansowanego.
- Statystyki są rozwijanym elementem na początku Planów nauczycieli.
- Wyłączone zasady są szare.
- Kolejność zasad jest automatycznie zapisywana po przeciągnięciu.
- Karta „Nauczyciele” pozwala dodawać osoby, aktywować/dezaktywować je i zmieniać kategorię ogólny / 1–3 / WF.
- Karta „Panel nauczyciela” pozwala skopiować indywidualny link. Nauczyciel widzi tam własny plan i preferencje.
- Wpływ wariantu pokazuje dokładne dodane i usunięte dyżury wraz z miejscem i oczekiwaniem.

### Punkt odniesienia dla zastępstw
Przycisk „Ustal bieżący plan jako punkt odniesienia dla zastępstw” nie publikuje niczego na stronie ani nauczycielom. Zapisuje migawkę planu, do której tryb operacyjny porównuje późniejsze zastępstwa. Dzięki temu solver może minimalizować liczbę zmian po nieobecności nauczyciela.

## Preflight i automatyczne wyjątki (v5.53)
Przed uruchomieniem pełnego solvera aplikacja wykonuje szybki test warunków koniecznych. Jeśli reguła ustawiona jako „Musi być” uniemożliwia wymaganą obsadę, ale sama obsada nadal wynika z aktywnej strefy szkoły, aplikacja nie usuwa stanowiska. Zamiast tego zmienia udowodnioną jako niewykonalną regułę na „Zalecane 5 — Najwyższa” i pokazuje, ilu wyjątków potrzeba co najmniej oraz których slotów problem dotyczy.

Automatyczne 0 w obsadzie może wynikać wyłącznie z planu lekcji: po zakończeniu zajęć w danej strefie. Kolizje z lekcją, ręczne blokady, podwójny przydział i dyżur w dniu bez lekcji pozostają regułami nienaruszalnymi. Jeżeli taki blocker nadal uniemożliwia obsadę, CP-SAT nie startuje i użytkownik dostaje komunikat o przyczynie.

## Widoczne wyjątki i statystyki (v5.54)
Jeśli preflight automatycznie obniży niewykonalną regułę z „Musi być” do „Zalecane 5 — Najwyższa”, nad planem 1–3, planem całej szkoły i zakładką Statystyki pojawia się żółty komunikat. Po rozwinięciu pokazuje on przyczynę, minimalną liczbę koniecznych wyjątków oraz sloty, których dotyczy dowód niewykonalności.

W grupie „Plan dyżurów” dostępna jest zakładka „Statystyki”. Pokazuje zapisany plan, nie szkic roboczy. Tabela zawiera liczbę lekcji, liczbę i minuty dyżurów, podział 1–3/szkoła, długie przerwy, oczekiwanie, obciążenie na poszczególne dni oraz wskaźnik minut dyżuru na jedną lekcję. Domyślnie największe obciążenie minutowe jest na górze.
## Jak czytać długie przerwy w szkicu (v5.55)
Panel szkicu pokazuje teraz osobno trzy rzeczy. „Udowodnione minimum przez preflight” oznacza dolną granicę wymuszoną przez plan lekcji i wymaganą obsadę. „Kandydaci wskazani przez preflight” to osoby, które mogą pokryć konieczny wyjątek, gdy analizowana reguła zostanie poluzowana. „W tym konkretnym szkicu faktycznie” opisuje natomiast bieżący nieoptymalny wariant i może zawierać dużo więcej wyjątków niż minimum.

Liczba „przydziałów” nie jest liczbą długich przerw. Jedna długa przerwa może mieć kilka równoległych miejsc dyżuru, dlatego np. 10 długich przerw może dać kilkadziesiąt przydziałów. Interfejs pokazuje teraz również liczbę różnych długich przerw i pozwala rozwinąć rozkład po konkretnych slotach.

Jeżeli widnieje komunikat „Preflight nie wykazał, że taki wyjątek jest konieczny”, oznacza to, że szybki test warunków koniecznych nie znalazł powodu, dla którego reguła musiałaby zostać naruszona. Takie naruszenia w roboczym szkicu należy traktować jako materiał do dalszej optymalizacji, a nie jako konieczny kompromis.
## Statystyki na żywo (v5.57)
Zakładka „Statystyki” domyślnie śledzi najlepszy szkic aktualnie znajdowany przez Generator. Gdy solver znajduje lepszy wariant, tabela, KPI, paski obciążenia oraz wykresy aktualizują się automatycznie przy następnym odpytywaniu statusu — zwykle w czasie krótszym niż sekunda.

Nad statystykami widoczna jest informacja o źródle. „NA ŻYWO — najlepszy szkic #…” oznacza dane z bieżącego wyszukiwania. Jeśli nie ma jeszcze pełnego szkicu, aplikacja tymczasowo pokazuje zapisany plan. Po wyłączeniu opcji „automatycznie śledź najlepszy szkic solvera” statystyki zawsze pokazują wyłącznie zapisany plan produkcyjny.

Jeżeli wyszukiwanie stało się nieaktualne po ręcznej zmianie danych, zostało anulowane albo zakończyło się błędem, szkic nie jest używany jako źródło statystyk.
## Jeden plan na wszystkich ekranach (v5.58)
Gdy Generator ma już pełny szkic dla obu zakresów, ekrany administracyjne „Korytarz 1–3”, „Cała szkoła”, „Plany nauczycieli” i „Statystyki” pokazują dokładnie ten sam szkic. Dotyczy to również mapy miejsc, liczników obsady, informacji o oczekiwaniu i wykresów. Przy znalezieniu lepszego pełnego wariantu widoki przełączają się automatycznie przy następnym pollingu statusu.

Nad ekranami znajduje się pasek źródła. Zielony status „NA ŻYWO — najlepszy pełny szkic #…” oznacza niezapisany wynik Generatora. Wyłączenie globalnego przełącznika live powoduje natychmiastowy powrót wszystkich ekranów do planu zapisanego. Jeśli Generator nie ma jeszcze pełnego wariantu, nie pokazujemy mieszanki starego i nowego planu — wszystkie ekrany pozostają na zapisanym planie.

Ręczna edycja szkicu live wymaga jawnego przyjęcia go jako bazy. Publiczny portal nauczyciela nie publikuje roboczych szkiców i nadal pokazuje wyłącznie plan zapisany/publikowany.

## Realny plan człowieka (v5.60)
Pełny plan nie wystarcza, jeśli jest fizycznie nierozsądny. Generator traktuje teraz limity kolejnych dyżurów, dzienne, tygodniowe i limity długich przerw jako chronione limity człowieka. Szybki szkic nie może ich poluzować tylko po to, aby szybciej uzyskać 100% obsady.

Domyślna wartość „Maks. dyżurów następujących po sobie” wynosi teraz 1. Oznacza to, że po dyżurze nauczyciel musi mieć następną przerwę wolną. Jeśli w przyszłości administrator świadomie zmieni tę wartość, aplikacja jej nie cofnie.

Jeżeli przy chronionych limitach nie da się znaleźć pełnego planu, Generator ma szukać innych ustępstw komfortu albo zgłosić brak realnego rozwiązania; nie wolno mu po cichu zamienić nauczyciela w osobę dyżurującą na każdej przerwie.

## Mapa obłożenia sal (v5.60.1)
Wejdź na /map. Kolor sali pokazuje tygodniowe wykorzystanie: jasna sala ma mało lekcji, ciemnoczerwona ma dużo lekcji. Liczba w sali ma format zajęte/45 i nie oznacza liczby komputerów.

Kliknij salę, aby otworzyć plan sali. Tabela ma dni Pn–Pt i lekcje 1–9. Zajęty slot pokazuje klasę, przedmiot i nauczyciela, a wolny slot jest oznaczony jako „wolna”. Dzięki temu można znaleźć okienka w wykorzystaniu sal.

Źródłem danych jest ten sam zaimportowany plan lekcji nauczycieli, którego używa solver. Heat mapa liczy unikalny slot sali tylko raz, nawet jeśli w tym samym czasie w danych występuje kilku nauczycieli lub kilka wpisów grupowych.

## Wygaszanie dyżurów 1–3 (v5.60.2)
Dla każdej strefy dyżur obowiązuje do przerwy bezpośrednio po ostatniej lekcji w tej strefie. Jeżeli po tej przerwie nie ma już kolejnych lekcji, następne sloty mają obsadę 0.

Indywidualna reguła „Wymagaj tego nauczyciela w slocie” nie może tworzyć dyżuru w nieaktywnym slocie 1–3. Taka reguła jest automatycznie usuwana. To samo dotyczy ręcznej próby podniesienia obsady przez API.

## Kolejność grup na korytarzu 1–3 (v5.62)
Dla dyżurów 1–3 Generator stosuje hierarchię: nauczyciele 1–3 → nauczyciele ogólni → WF. Nauczyciel spoza 1–3 nie jest zakazany, ponieważ w niektórych slotach fallback jest konieczny do pełnej obsady. Solver najpierw minimalizuje liczbę wszystkich outsiderów, a następnie — bez zwiększania tej liczby — minimalizuje wykorzystanie WF. Dzięki temu WF trafia na korytarz 1–3 dopiero wtedy, gdy nie da się uzyskać równie kompletnego rozwiązania z nauczycielem ogólnym.

Ta reguła jest strukturalnym etapem CP-SAT, nie zwykłym if-em ani słabą wagą. Szybkie szkice nie mogą jej wyłączyć. Diagnostyka solvera pokazuje minimum outsiderów oraz minimum WF fallbacków.

## WF jako późny fallback (v5.77)

Nauczyciele oznaczeni kategorią WF są traktowani jako grupa awaryjna ze względu na większą odległość od typowych miejsc dyżuru. Sam fakt, że nauczyciel WF znajduje się w zapisanej puli, nie oznacza już, że Generator może użyć go od początku.

Generator najpierw szuka pełnego planu bez WF, wykorzystując nauczycieli właściwej grupy, nauczycieli ogólnych, przetasowania oraz dopuszczalne zmiany limitów. Dopiero po wyczerpaniu tych możliwości otwiera fazę WF. Jeszcze później może rozważyć długą przerwę po ostatniej lekcji, a dodatkowe oczekiwanie pozostaje absolutnie ostatnim fallbackiem.

Jeżeli administrator ustawił konkretnemu nauczycielowi WF stały przydział, taki przydział pozostaje obowiązujący. Po otwarciu fazy WF Solver minimalizuje liczbę dyżurów WF i Diagnostyka pokazuje ich liczbę osobno dla 1–3, całej szkoły i łącznie.

## v5.77 plan source status

The source banner has one meaning on every screen:
- live_verified: current verified full solver result;
- saved_verified: saved plan with real full coverage;
- reference_verified: last verified full plan used while a new search is still running;
- invalid_saved: saved state does not have real full coverage.

Completeness means a real teacher on every required position. Eighty empty 1-3 records
mean zero filled positions, not a complete plan.


## Preferencje nauczyciel × miejsce (v5.78)

Wejdź w **Miejsca dyżurów**. Na końcu widoku znajduje się tabela, w której wiersz oznacza nauczyciela, a kolumna konkretne miejsce dyżuru.

- 1,00 — miejsce naturalne / mocno preferowane,
- 0,75 i 0,50 — preferencja pośrednia,
- 0,25 — słaby fallback,
- 0,00 — kosztowny fallback, ale nie zakaz.

Do twardego wyłączenia używaj blokad i reguł hard, nie wartości 0.

Lista miejsc jest wspólna. **Sala gimnastyczna A** i **Sala gimnastyczna B** są miejscami systemowymi: nie można ich usunąć ani przemianować, a Solver może przydzielać tam wyłącznie WF. Obsada A/B jest automatycznie wyliczana z planu zajęć sportowych.
