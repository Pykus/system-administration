# DEMO Duty Planner v5.24

## Jawna zmiana zasady algorytmu
Przed szerokim CP-SAT działa tani precheck warunków koniecznych.

Kolejność:
1. minimalna pojemność max_week / max_day,
2. dostępność konkretnego slotu przy aktualnych twardych regułach,
3. oczywiste korekty: minimalnie potrzebny limit, dodanie nauczyciela do puli bez naruszania twardych reguł, lokalne zmniejszenie niewykonalnej obsady,
4. szerokie warianty organizacyjne,
5. reguły komfortu,
6. avoid_wait i 3+ kolejnych dyżurów — absolutnie na końcu.

Obsada nie jest obniżana automatycznie ani arbitralnie. Precheck może zaproponować lokalne obniżenie tylko dla slotu, którego obecnej obsady nie da się osiągnąć przy aktualnych twardych regułach.

## Testy
- app.py kompiluje się,
- precheck bieżącego stanu: około 67 ms,
- sztuczne max_week=1/max_day=1 -> minimalne rekomendacje max_week=9, max_day_13=2, max_day_school=2,
- slot-level matching wykrywa konkretne niedobory oraz kandydatów spoza puli,
- end-to-end na 8092: etap Szybki test wykonalności widoczny przed pełnym solve,
- po baseline pierwsza faza to preflight-obvious, przed tier-ceiling,
- solver_ortools.py bez zmian.

## Worker farm
- protokół 5.15 bez zmian,
- docelowa paczka workera 1.8.
