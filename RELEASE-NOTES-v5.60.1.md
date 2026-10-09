# RELEASE NOTES v5.60.1 — mapa obłożenia sal

## Cel
Mapa budynku służy teraz do analizy wykorzystania sal, a nie do inwentaryzacji komputerów.

## Zmiany
- usunięto z mapy liczniki, kropki i listy komputerów;
- dane mapy są pobierane z bieżącego planu lekcji przez /api/map/lessons;
- obłożenie liczone jest jako unikalne sloty sala × dzień × godzina lekcyjna, maksymalnie 45 tygodniowo;
- kolor sali jest heat mapą: im więcej zajętych slotów, tym ciemniejsza czerwień;
- każda sala pokazuje zajęte/łączne sloty;
- kliknięcie sali otwiera plan Pn–Pt, lekcje 1–9, z klasą, przedmiotem i nauczycielem;
- wolne sloty są jawnie oznaczone, dzięki czemu widać okienka;
- zachowano zoom, przesuwanie, dotyk i geometrię mapy;
- identyczna funkcja została przeniesiona do niedeployowanej gałęzi v5.61, aby przyszłe wdrożenie nie cofnęło mapy.

## Testy
- test_v5601_room_heatmap.py: agregacja unikalnych slotów, brak warstwy komputerów, obecność heat mapy/modalu i zachowanie kluczowych sal;
- Python compile i JavaScript node --check;
- test API na rzeczywistych danych: 44 oznaczenia sal; sala 123: 29/45 zajętych slotów w chwili wdrożenia.
