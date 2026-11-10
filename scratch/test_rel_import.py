import runpy, tempfile, os, sys, re

d = tempfile.mkdtemp()
with open(os.path.join(d, "database.py"), "w") as f:
    f.write("engine = 'fake_engine'\nBase = 'fake_base'\nSessionLocal = 'fake_session'\n")

with open(os.path.join(d, "main.py"), "w") as f:
    f.write("from .database import engine, Base, SessionLocal\nprint('SUCCESSFULLY LOADED:', engine, Base, SessionLocal)\n")

abs_sp = os.path.join(d, "main.py")
sp_dir = d
if sp_dir not in sys.path:
    sys.path.insert(0, sp_dir)

src = open(abs_sp, "r", encoding="utf-8", errors="ignore").read()
healed = re.sub(r"\bfrom\s+\.([a-zA-Z0-9_]+)\s+import\b", r"from \1 import", src)
print("Healed code:")
print(healed)
code_obj = compile(healed, abs_sp, "exec")
globs = {"__name__": "__main__", "__file__": abs_sp}
exec(code_obj, globs)
print("EXEC SUCCEEDED! Result:", globs.get("engine"))
