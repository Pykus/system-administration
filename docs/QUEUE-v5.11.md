# Kolejka v5.11 — przed następnym wdrożeniem

- Usunąć pusty biały kontener/panel widoczny w interfejsie Planera, który renderuje się bez treści.
  - zidentyfikować dokładny `card/div`,
  - nie renderować kontenera, jeśli jego zawartość jest pusta/warunkowo ukryta,
  - sprawdzić wszystkie główne zakładki pod kątem podobnych pustych bloków,
  - dodać test UI/regresyjny potwierdzający brak pustych kontenerów po renderowaniu.
