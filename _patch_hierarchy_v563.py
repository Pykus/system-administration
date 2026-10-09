from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools\app.py")
s=p.read_text(encoding="utf-8")
s=s.replace('hardened.update({"avoid_wait","after_last_long","before_first_long"})','hardened.add("avoid_wait")')
s=s.replace('job["_working_hardened"]=["avoid_wait","after_last_long","before_first_long"]','job["_working_hardened"]=["avoid_wait"]')
start=s.index("        jump_specs=[")
end=s.index("        with REPAIR_JOB_LOCK:",start)
new='''        jump_specs=[
            (["after_last_long","before_first_long"],0,3,"scisly skok - bez dlugiej przerwy przed/po krawedzi dnia"),
            (["after_last_long","before_first_long"],17,4,"scisly skok - alternatywny seed"),
            (["after_last_long","before_first_long"],41,5,"scisly skok - trzeci uklad"),
            (["after_last_long"],73,4,"pozny fallback - mozliwy wyjatek przed pierwsza lekcja"),
            ([],101,4,"ostatni fallback krawedzi dnia - po ostatniej lekcji dopiero tutaj"),
        ]
'''
s=s[:start]+new+s[end:]
p.write_text(s,encoding="utf-8")
print("hierarchy patched")