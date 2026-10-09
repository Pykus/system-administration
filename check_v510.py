from pathlib import Path
import re
root=Path(r'C:\DutySolverDemo\dyzury-v5.10-ortools')
h=(root/'static'/'index.html').read_text(encoding='utf-8')
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',h,re.S|re.I)
(root/'_ui_check_v510.js').write_text(scripts[-1],encoding='utf-8')
for x in ['Dyżury v5.10','Generator wariantów naprawczych','Pauza','Wznów','max_consecutive_duties']:
    assert x in h,x
print('UI_MARKERS_OK',len(scripts))
