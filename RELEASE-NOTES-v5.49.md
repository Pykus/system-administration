# RELEASE NOTES v5.49 — usunięcie „Unikaj wydłużania dnia pracy”

Zakres wydania: wyłącznie całkowite usunięcie constraintu day_span_penalty.

- usunięto definicję z globalnych constraintów;
- usunięto funkcję kosztu i liczenie z OR-Tools CP-SAT;
- usunięto z Generatora wariantów i indywidualnych ustępstw;
- usunięto z portalu/katalogu ustępstw nauczyciela;
- usunięto etykietę z interfejsu;
- migracja usuwa stary klucz z state.json, teacher_relax_order, teacher_relaxed_rules,
  repair_guidance, solver_weight_overrides i zapisanych wariantów;
- zapisane profile ustawień są automatycznie oczyszczane i zapisywane ponownie;
- normalize_constraint_rows odrzuca stary klucz, więc stary profil/wariant/API nie może go przywrócić;
- jedyne pozostawione wystąpienie nazwy klucza w kodzie backendu to tombstone migracyjny REMOVED_CONSTRAINT_KEYS.

TDD: 5 nowych testów.
Pełny gate przed wdrożeniem: 77/77 OK + Python compile + JS syntax.
