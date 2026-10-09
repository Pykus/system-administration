from pathlib import Path
repls={
"test_v53.py":[('app.health()["version"],"5.4"','app.health()["version"],"5.5"')],
"test_v54.py":[('app.app.version,"5.4"','app.app.version,"5.5"'),('app.health()["version"],"5.4"','app.health()["version"],"5.5"'),('dyzury-v5.4-ortools','dyzury-v5.5-ortools')],
"deployment_test_local.py":[('info["version"]!="5.4"','info["version"]!="5.5"')],
"start_service.cmd":[('dyzury-v5.4-ortools','dyzury-v5.5-ortools')],
}
for fn,pairs in repls.items():
    p=Path(fn); s=p.read_text(encoding="utf-8")
    for a,b in pairs: s=s.replace(a,b)
    p.write_text(s,encoding="utf-8")

p=Path("run_local_test_suite.py")
s=p.read_text(encoding="utf-8")
s=s.replace('"test_v54.py","deployment_test_local.py"','"test_v54.py","test_v55.py","deployment_test_local.py"')
s=s.replace('"version":"5.4"','"version":"5.5"')
s=s.replace('TEST_REPORT_v5.4.json','TEST_REPORT_v5.5.json')
p.write_text(s,encoding="utf-8")

readme=Path("README.md")
r=readme.read_text(encoding="utf-8")
r=r.replace("# DEMO Dyżury v5.4 – OR-Tools","# DEMO Dyżury v5.5 – OR-Tools")
if "## v5.5" not in r:
    r=r.replace("## Najważniejsze funkcje","## v5.5\n- Naprawiono błąd HTTP 500 po zapisaniu pustego seeda; seed jest teraz wewnętrzny i automatycznie normalizowany.\n- Diagnostyka proponuje wyłącznie warianty dające 100% obsady.\n- Najpierw próbuje przeorganizować plan 1–3 i plan całej szkoły bez luzowania constraintów; dopiero później rozważa zmianę „Musi być” na „Zalecane”.\n- Wariant pokazuje liczbę zmienionych stanowisk oraz imienną listę nauczycieli z dodanymi/usuniętymi dyżurami.\n- „Unikaj dodatkowego oczekiwania” ma wysoki koszt poluzowania i jest rozważane później niż mniej obciążające zmiany.\n- Nauczyciele ogólni dla 1–3 są najpierw dobierani spośród osób uczących klas 1–3 lub mających zajęcia w salach korytarza 1–3.\n- Szerokie tabele mają strony po 12 nauczycieli; listy nauczycieli są alfabetyczne.\n- Szczegóły techniczne solvera są schowane w rozwijanej sekcji.\n\n## Najważniejsze funkcje")
r=r.replace("v5.4: zapisane nieobecności","v5.4: zapisane nieobecności")
r=r.replace("test scalający v5.4","testy regresyjne v5.4 i v5.5")
readme.write_text(r,encoding="utf-8")

ch=Path("docs/CHANGELOG.md")
c=ch.read_text(encoding="utf-8")
if "## 5.5" not in c:
    c=c.replace("# CHANGELOG\n","# CHANGELOG\n\n## 5.5 – 2026-09-19\n- Naprawiono HTTP 500 powodowane pustą wartością solver_seed.\n- Seed ukryto przed zwykłym użytkownikiem; backend bezpiecznie używa wartości domyślnej.\n- Automatyczne propozycje przeniesiono na górę Diagnostyki i pokazują wyłącznie warianty 100%.\n- Dodano priorytet przeorganizowania planów bez luzowania constraintów oraz semantyczny koszt poluzowania reguł; dodatkowe oczekiwanie jest kosztowne.\n- Dodano Minimal Perturbation do wyliczania wpływu wariantu i imienną listę zmian nauczycieli.\n- Awaryjne włączenie nauczycieli ogólnych preferuje osoby powiązane z klasami/salami 1–3.\n- Dodano stronicowanie szerokich planów po 12 nauczycieli i alfabetyczne sortowanie list.\n- Uproszczono UI: diagnostyka techniczna i ustawienia solvera są rozwijane.\n")
ch.write_text(c,encoding="utf-8")
print("release files patched")

