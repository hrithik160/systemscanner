import re
from pathlib import Path

def test_extract_node_module_not_found():
    sample_error = """
    node:internal/modules/cjs/loader:1208
      throw err;
      ^

    Error: Cannot find module 'express'
    Require stack:
    - C:\\Users\\tms_s\\AppData\\Local\\Temp\\workspace\\server.js
        at Module._resolveFilename (node:internal/modules/cjs/loader:1205:15)
        at Module._load (node:internal/modules/cjs/loader:1031:27)
        at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:174:12)
        at node:internal/main/run_main_module:28:49 {
      code: 'MODULE_NOT_FOUND',
      requireStack: [
        'C:\\\\Users\\\\tms_s\\\\AppData\\\\Local\\\\Temp\\\\workspace\\\\server.js'
      ]
    }
    """
    m = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", sample_error)
    assert m is not None
    assert m.group(1) == "express"
    print("Extracted package:", m.group(1))

    # Test missing file error:
    sample_file_error = """
    Error: Cannot find module 'C:\\Users\\tms_s\\workspace\\server.js'
    code: 'MODULE_NOT_FOUND',
    requireStack: []
    """
    m2 = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", sample_file_error)
    assert m2 is not None
    print("Extracted file:", m2.group(1))

test_extract_node_module_not_found()
print("Regex tests passed!")
