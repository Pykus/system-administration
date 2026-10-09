# DEMO Dyżury v5.15 — 2026-09-19

- Poprawiono interpretację sentinela oczekiwania: wartość 9 oznacza dzień bez lekcji / przyjazd tylko na dyżur, a nie 9 lekcji oczekiwania.
- W wariantach naprawczych nazwisko nauczyciela otwiera modal z planem lekcji oraz dyżurami przed/po.
- Dodano trwałe „Wyklucz ze wszystkich dyżurów”; lista jest nadrzędna wobec pul, stałych przydziałów i generatora.
- Dodano „Zamroź skład puli” osobno dla 1–3 i całej szkoły.
- Pula całej szkoły: Tylko zwykli, +WF awaryjnie, +1–3 awaryjnie, Nikt.
- Braki 1–3: osobne przyciski dodania nauczycieli ogólnych i WF oraz osobny Przelicz.
- Puste pule są rzeczywiście puste; wymagany/zamrożony nauczyciel spoza puli nie omija już listy dopuszczonych.
- Nazwy wyświetlane są jako „Nazwisko Imię”; sortowanie list nauczycieli odbywa się po nazwisku (część nazwiskowa może być wieloczłonowa).
- Generator respektuje zamrożone pule i globalne wykluczenia.
- Usunięto powtarzające się opisy zmian w diagnostyce.
- Worker protocol pozostaje 5.12 — obecna paczka workerów pozostaje zgodna.
