from pathlib import Path
import json,zipfile,hashlib,datetime
root=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools")
out=Path(r"C:\DutySolverDemo\releases"); out.mkdir(exist_ok=True)
notes=root/"RELEASE-NOTES-v5.10.md"
txt=notes.read_text(encoding="utf-8")
txt += """

## ADM02 / plan lekcji
- DEMO-ADM02 odpowiada w sieci (192.0.2.0.100), ping i RDP są dostępne.
- Agent Remote Desktop Commander na ADM02 jest offline.
- Brak aktywnej sesji użytkownika na ADM02 (quser nie zwraca użytkownika).
- Dostęp do udziału administracyjnego C$ z NODE00 jest odrzucony.
- Weryfikacja planów w zalogowanym dzienniku pozostaje oczekująca; wykonać po zalogowaniu użytkownika lub uruchomieniu agenta na ADM02.
"""
notes.write_text(txt,encoding="utf-8")
(root/"docs"/"ADM02-PLAN-VERIFICATION-PENDING.md").write_text("""# ADM02 — weryfikacja planów nauczycieli

Status: OCZEKUJE.

Cel: na DEMO-ADM02 w dzienniku odtworzyć aktualne plany nauczycieli na podstawie planów poszczególnych klas i porównać je z data/seed.json.

Stan 2026-09-19:
- host DEMO-ADM02 / 192.0.2.0.100 odpowiada,
- RDP odpowiada,
- brak aktywnej sesji użytkownika,
- Remote Desktop Commander offline,
- NODE00 nie ma dostępu do C$.

Nie kopiować/obchodzić danych logowania. Kontynuować po uruchomieniu sesji użytkownika/Commandera na ADM02.
""",encoding="utf-8")

zp=out/"DEMO-Dyzury-v5.10-2026-09-19.zip"
skip={"patch_v510.py","patch_test2_v510.py","check_v510.py","_ui_check_v510.js","smoke_repair_job_v510.py","run_stage_v510.cmd","deploy_v510.py","baseline_status_check.py","alternative_variants_audit.py","school_unresolved_check.py","variant_diagnostic_extra.py","build_release_v510.py"}
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in root.rglob("*"):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        if "__pycache__" in rel.parts or "logs" in rel.parts or any(x.startswith("predeploy-") for x in rel.parts) or p.name in skip:
            continue
        z.write(p,(Path("dyzury-v5.10-ortools")/rel).as_posix())
with zipfile.ZipFile(zp) as z: bad=z.testzip()
sha=hashlib.sha256(zp.read_bytes()).hexdigest()
report={
 "version":"5.10",
 "deployed_at":datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
 "production":"http://127.0.0.1:8091","localhost_only":True,"engine":"OR-Tools CP-SAT",
 "tests":"7/7 PASS; compileall PASS; node --check PASS; async repair start/pause/resume/cancel PASS",
 "features":["progressive repair search","incremental variants","progress bar","pause/resume/cancel","staffing 2->1 candidate","school position 1->0 candidate","numeric limit variants","pool expansion","comfort-last ranking","max consecutive duties default 1"],
 "state_preserved":{"school_assignments":354,"rows13":50},
 "adm02_plan_verification":"pending: host online but no user session, RDC offline, C$ denied",
 "zip":str(zp),"bytes":zp.stat().st_size,"sha256":sha,"integrity":"PASS" if bad is None else "FAIL:"+str(bad),
 "rollback":r"C:\DutySolverDemo\dyzury-v5.9-ortools"
}
(root/"DEPLOYMENT-REPORT-v5.10.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
(out/"DEMO-Dyzury-v5.10-2026-09-19.BUILD.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
