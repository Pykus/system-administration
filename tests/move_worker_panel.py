from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.78-ortools\static\index.html")
s=p.read_text(encoding="utf-8")
start=s.index('<div class="card worker-farm" v-if="workerFarm">')
end=s.index('\n<div class="actions" style="margin-top:8px">', start)
worker=s[start:end]
s=s[:start]+s[end:]
insert=s.index('\n<div v-if="repairJob?.search_policy"')
s=s[:insert]+"\n"+worker+"\n"+s[insert:]
p.write_text(s,encoding="utf-8")
print("moved worker farm below live solver status:", s.index('data-solver-mini-terminal') < s.index('class="card worker-farm"'))