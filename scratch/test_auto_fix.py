from pathlib import Path
from app.llm.knowledge import auto_fix_runtime_error

# Test 1: Python relative import
test_error_1 = """
Traceback (most recent call last):
  File "main.py", line 5, in <module>
    from .database import engine, Base, SessionLocal
ImportError: attempted relative import with no known parent package
"""
res1 = auto_fix_runtime_error("pid1", test_error_1, Path("."))
print("Result 1:", res1)

# Test 2: Node MODULE_NOT_FOUND
test_error_2 = """
code: 'MODULE_NOT_FOUND',
requireStack: []
"""
res2 = auto_fix_runtime_error("pid2", test_error_2, Path("."))
print("Result 2:", res2)

print("Tests completed successfully!")
