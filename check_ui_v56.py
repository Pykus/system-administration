from pathlib import Path
import re
h=Path("static/index.html").read_text(encoding="utf-8")
b=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",h,re.S|re.I)
Path("_ui_check_v56.js").write_text(b[-1],encoding="utf-8")
print("scripts",len(b))
print("constraints_tabs",h.count("mainTab==='constraints'"))
print("stats_tabs",h.count("mainTab==='stats'"))
print("rulesDetails",h.count('id="rulesDetails"'))
print("teacherAdmin",h.count("mainTab==='teacherAdmin'"))
print("teacherPortal",h.count("mainTab==='teacherPortal'"))
