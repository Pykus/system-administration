from pathlib import Path
import re
h=Path('static/index.html').read_text(encoding='utf-8')
b=re.findall(r'<script(?:\\s[^>]*)?>(.*?)</script>',h,re.S|re.I)
Path('_ui_check_v58.js').write_text(b[-1],encoding='utf-8')
print('scripts',len(b))
for x in ['teacherPageSize:15','Efektywny wsp.','Wymagana liczba dyżurujących','Wymagana obsada stanowisk','polityka stała']:
 print(x,h.count(x))
t=Path('static/teacher.html').read_text(encoding='utf-8')
for x in ['Plan tygodnia','class="schedule"','Godzina','Moje dyżury']:
 print('teacher',x,t.count(x))
