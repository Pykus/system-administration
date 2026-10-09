# Kolejka v5.10 — NIE WDRAŻAĆ JESZCZE

1. Constraint: maksymalna liczba dyżurów następujących bezpośrednio po sobie.
   - parametr liczbowy,
   - preferowany domyślny limit: 1,
   - wariant łagodniejszy: 2,
   - constraint ma działać osobno jako HARD/SOFT i być uwzględniany przez diagnostykę wariantów.

2. Zweryfikować na DEMO-ADM-02 w dzienniku aktualne plany nauczycieli.
   - źródło: plany poszczególnych klas,
   - odtworzyć z nich plan każdego nauczyciela,
   - porównać z seed.json/planami używanymi przez solver,
   - nie zmieniać danych produkcyjnych bez osobnej walidacji.

3. Przebudować generator wariantów naprawczych tak, aby preferował warianty bez pogarszania wygody nauczycieli:
   - przesunięcia innych nauczycieli,
   - większa/nieregularna liczba dyżurów,
   - zmiany limitów liczbowych,
   - zmiany puli nauczycieli,
   - relaks preferencji i limitów przed relaksem avoid_wait / day-span / before-first / after-last.
