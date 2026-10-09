
from pathlib import Path
import re
root=Path(__file__).parent
h=(root/"static"/"index.html").read_text(encoding="utf-8")
scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",h,re.S|re.I)
(root/"_ui_check_v512.js").write_text(scripts[-1],encoding="utf-8")
for x in ("Dyżury v5.12","nierozstrzygnięte","grupa 1–3 jest zawsze wykluczona","To nie jest dowód braku rozwiązania"):
    assert x in h,x
assert "+ 1–3 awaryjnie" not in h
print("UI_STATIC_OK",len(scripts))
