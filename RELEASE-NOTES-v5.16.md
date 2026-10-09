# DEMO Dyżury v5.16 — 2026-09-19

Najważniejsza poprawka generatora wariantów:
- wykrywa twardy deficyt pojemności puli (np. 11 nauczycieli × maks. 8 = 88 < 95 wymaganych),
- przy deficycie natychmiast uruchamia głębokie próby minimalnych zmian pojemności wraz z ostatnią możliwością avoid_wait -> soft,
- pełny wariant awaryjny jest potwierdzany wcześnie, ale w UI nadal pozostaje oznaczony jako OSTATNIA MOŻLIWOŚĆ i sortowany za wariantami bez oczekiwania,
- generator dalej szuka lepszego wariantu po znalezieniu fallbacku,
- zapisuje capacity13/capacitySchool, confirmed_fallback i checkpointy.

Test na aktualnym stanie produkcyjnym:
- 1–3: 95/95,
- cała szkoła: 354/354,
- 0 braków,
- status rozstrzygnięty,
- pełny wariant znaleziony przez kombinację zwiększającą pojemność puli 1–3 + zmiękczenie avoid_wait.

Workery:
- protokół pozostaje 5.15 niezależnie od wersji Planera,
- istniejący Worker v1.3 pozostaje zgodny z v5.16.
