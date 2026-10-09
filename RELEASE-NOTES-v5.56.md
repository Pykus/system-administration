# RELEASE NOTES v5.56 — jednoznaczna semantyka przerw

- Poprawiono nazewnictwo reguł `after_last_long` i `before_first_long`: są teraz opisywane jako **przerwa >5 min**, bo obejmują także przerwy 10-minutowe.
- Nie są już mylone z limitami „długich przerw”, dla których próg w solverze wynosi 15 minut.
- Panel szkicu nadal rozdziela: udowodnione minimum, kandydatów preflightu oraz faktyczne przydziały konkretnego szkicu.
- W przypadku braku dowodu konieczności wyjątku UI mówi wprost, że minimum wynosi 0 i solver powinien dalej eliminować takie przydziały.
- Lista nauczycieli pod szkicem oznacza wyłącznie osoby rzeczywiście przydzielone w tym wariancie, a nie osoby, które muszą dostać wyjątek.

Gate: 129/129 testów OK, Python compile OK, JS syntax OK.
