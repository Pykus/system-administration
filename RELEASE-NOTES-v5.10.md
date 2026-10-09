# DEMO Dyżury v5.10 — 2026-09-19

- Generator napraw został przebudowany z „poluzuj 1–2 twarde reguły” na progresywne przeszukiwanie wariantów.
- Sprawdzane są m.in.: pełny rebalance, zwiększenie limitów dyżurów, rozszerzenie puli nauczycieli, redukcja obsady 1–3 z 2 do 1 dla brakującego slotu, wyłączenie pojedynczego stanowiska szkoły, preferencje, blokady i dopiero na końcu reguły pogarszające komfort.
- Oczekiwanie / wcześniejsze przychodzenie / późniejsze zostawanie mają bardzo wysoki koszt rankingu.
- Warianty pojawiają się w UI natychmiast po znalezieniu; wyszukiwanie kontynuuje się w tle.
- Dodano orientacyjny pasek postępu, liczbę sprawdzonych wariantów oraz Pauza / Wznów / Zatrzymaj.
- Dodano constraint „Maks. dyżurów następujących po sobie”, domyślnie aktywny jako MUSI BYĆ z wartością 1.
- Zastosowanie wariantu odbywa się po przeglądzie i zapisuje dokładnie konfigurację sprawdzoną przez generator.


## ADM02 / plan lekcji
- DEMO-ADM02 odpowiada w sieci (192.0.2.0.100), ping i RDP są dostępne.
- Agent Remote Desktop Commander na ADM02 jest offline.
- Brak aktywnej sesji użytkownika na ADM02 (quser nie zwraca użytkownika).
- Dostęp do udziału administracyjnego C$ z NODE00 jest odrzucony.
- Weryfikacja planów w zalogowanym dzienniku pozostaje oczekująca; wykonać po zalogowaniu użytkownika lub uruchomieniu agenta na ADM02.
