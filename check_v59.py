from pathlib import Path
import re
root=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
h=(root/"static"/"index.html").read_text(encoding="utf-8")
scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",h,re.S|re.I)
(root/"_ui_check_v59.js").write_text(scripts[-1],encoding="utf-8")
for x in ["Dyżury v5.9","pokaż dyżury","Ustaw / zmień stały przydział","Preferencje zgłoszone przez nauczycieli","statsColumnFilters","teacherTimelineRows"]:
    assert x in h,x
assert "polityka stała" not in h
assert "<div><b>Plan dyżurów</b>" not in h
t=(root/"static"/"teacher.html").read_text(encoding="utf-8")
assert "stały przydział administratora" in t
print("UI_MARKERS_OK",len(scripts))
