from pathlib import Path
repls={
"start_service.cmd":[("dyzury-v5.5-ortools","dyzury-v5.6-ortools")],
"deployment_test_local.py":[('info["version"]!="5.5"','info["version"]!="5.6"')],
"test_v53.py":[('app.health()["version"],"5.5"','app.health()["version"],"5.6"')],
"test_v54.py":[('app.app.version,"5.5"','app.app.version,"5.6"'),('app.health()["version"],"5.5"','app.health()["version"],"5.6"'),("dyzury-v5.5-ortools","dyzury-v5.6-ortools")],
"test_v55.py":[('app.app.version,"5.5"','app.app.version,"5.6"'),('app.health()["version"],"5.5"','app.health()["version"],"5.6"')],
}
for fn,pairs in repls.items():
    p=Path(fn); s=p.read_text(encoding="utf-8")
    for a,b in pairs: s=s.replace(a,b)
    p.write_text(s,encoding="utf-8")

p=Path("run_local_test_suite.py"); s=p.read_text(encoding="utf-8")
s=s.replace('"test_v55.py","deployment_test_local.py"','"test_v55.py","test_v56.py","deployment_test_local.py"')
s=s.replace('"version":"5.5"','"version":"5.6"')
s=s.replace("TEST_REPORT_v5.5.json","TEST_REPORT_v5.6.json")
p.write_text(s,encoding="utf-8")

r=Path("README.md").read_text(encoding="utf-8")
r=r.replace("# DEMO Dyżury v5.5 – OR-Tools","# DEMO Dyżury v5.6 – OR-Tools")
if "## v5.6" not in r:
    r=r.replace("## v5.5","""## v5.6
- Zwężono stałe kolumny Godzina/Slot i zachowano stronicowanie po 12 nauczycieli.
- Kolejność zasad „Zalecane” jest trwała i służy tylko jako rozstrzygnięcie pomocnicze przy tym samym priorytecie; „Musi być” obowiązują równocześnie.
- Wyłączone zasady są wyszarzone; opisy używają wyłącznie „Musi być / Zalecane”.
- Warianty pełnej obsady pokazują dokładne dodane/usunięte dyżury nauczycieli i informację o oczekiwaniu.
- Dodano trwały rejestr nauczycieli z kategoriami ogólny / 1–3 / WF i automatyczne dopisywanie nowych osób z importu PDF.
- Dodano ograniczony panel nauczyciela /teacher z indywidualnym tokenem, własnym planem i własnymi preferencjami.
- Reguły / zasady przydziału przeniesiono pod Planowanie zaawansowane; Statystyki pod Plany nauczycieli.
- Przycisk publikacji planu przemianowano na punkt odniesienia dla zastępstw i wyjaśniono jego działanie.
- Strefy przejścia mają opisaną skalę 1–10.

## v5.5""")
Path("README.md").write_text(r,encoding="utf-8")

ch=Path("docs/CHANGELOG.md"); c=ch.read_text(encoding="utf-8")
if "## 5.6" not in c:
    c=c.replace("# CHANGELOG\n","# CHANGELOG\n\n## 5.6 – 2026-09-19\n- Uproszczono nawigację i język interfejsu.\n- Dodano trwały teacher_registry.json oraz panel zarządzania nauczycielami.\n- Import planów dodaje nowych nauczycieli i klasyfikuje ich do 1–3 / ogólnych / WF.\n- Dodano osobny panel /teacher z tokenem i własnymi preferencjami.\n- Rozszerzono diagnostykę wariantu o konkretne dodane/usunięte dyżury i oczekiwanie.\n- Kolejność zasad jest automatycznie zapisywana; wyłączone zasady są szare.\n- Reguły przeniesiono pod Planowanie zaawansowane, statystyki pod Plany nauczycieli.\n- Wyjaśniono punkt odniesienia dla zastępstw i skalę stref 1–10.\n")
    ch.write_text(c,encoding="utf-8")
print("release patched")
