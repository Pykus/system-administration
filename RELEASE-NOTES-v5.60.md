# RELEASE NOTES v5.60 — human-realistic duty plans

## Problem
Pełny szkic mógł być formalnie kompletny, ale nierealny dla człowieka: nauczyciel z ciągiem lekcji mógł dostać dyżur na kolejnych przerwach, a szybkie duże skoki mogły czasowo luzować twarde limity dzienne, tygodniowe i długich przerw.

## Zmiana polityki
- W szybkich/live szkicach sześć limitów człowieka jest zawsze chronionych: max kolejnych dyżurów, max dziennie 1–3, max dziennie szkoła, max tygodniowo, max długich dziennie, max długich tygodniowo.
- Te limity są również na liście NEVER_AUTO_RELAX: Generator nie może ich sam zmienić z MUSI BYĆ na ZALECANE.
- Jednorazowa migracja ustawia max kolejnych dyżurów z 2 na 1. W praktyce: po każdym dyżurze następna przerwa musi być wolna.
- Późniejsza ręczna zmiana administratora nie jest nadpisywana przez migrację.
- Dodatkowy filtr bezpieczeństwa odrzuca pełny szkic, jeśli mimo wszystko przekracza którykolwiek aktywny twardy limit człowieka.
- Widok live nie może pokazać wariantu oznaczonego jako nieludzki.

## Realny test na bieżącej kopii stanu
Pełne rozwiązanie istnieje bez łamania nowych limitów:
- 1–3: 70/70,
- szkoła: 385/385,
- missing: 0,
- najdłuższy ciąg dyżurów: 1,
- max dziennie: 4,
- max tygodniowo: 9,
- max długich dziennie: 1,
- max długich tygodniowo: 4,
- human_guardrail_ok: true.
Próba z limitem 3 dyżurów dziennie nie zakończyła się szybko w ograniczonym teście, dlatego nie zaostrzono tego limitu bez dowodu wykonalności.

## Testy
- 167/167 testów OK.
- Python compile OK.
- JavaScript node --check OK.
- Real-state full-solution probe: OK.
