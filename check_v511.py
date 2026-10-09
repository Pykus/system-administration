from pathlib import Path
import re
root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
h=(root/"static"/"index.html").read_text(encoding="utf-8")
scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",h,re.S|re.I)
(root/"_ui_check_v511.js").write_text(scripts[-1],encoding="utf-8")
for x in ["Dyżury v5.11","Przejrzyj wariant / zwiń szczegóły","Umożliw pracę zdalnym workerom","current_tokens"]:
    assert x in h,x
assert 'id="repairReview"' not in h
print("UI_STATIC_OK",len(scripts))
