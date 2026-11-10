import sys
import os
sys.path.insert(0, os.path.abspath('release-domino/backend'))

from app.llm.knowledge import guard_generated_code

sample = """import React, { useState } from 'react';
import { StrictNode } from 'react';

interface Props {
  title: string;
}

const AnimatedFeature: React.FC<Props> = () => {
  const [isVisible, setIsVisible] = useState(false);
  let timer: NodeJS.Timeout | null = null;

  const handleShow = () => {
    setIsVisible(true);
  };

  if (!isVisible) return null;

  const style: React.CSSProperties = {
    padding: '20px',
  };

  return <div style={style}>Hello World</div>;
};

export default AnimatedFeature;
export default OtherComp;
"""

result = guard_generated_code(sample, lang='jsx', file_path='frontend/src/AnimatedFeature.jsx')
print("=== GUARDIAN OUTPUT ===")
print(result)

assert "StrictNode" not in result, "StrictNode should be replaced"
assert "StrictMode" in result, "StrictMode should be present"
assert "React.FC" not in result, "React.FC should be stripped"
assert "NodeJS.Timeout" not in result, "NodeJS.Timeout should be stripped"
assert "React.CSSProperties" not in result, "React.CSSProperties should be stripped"
assert "interface Props" not in result, "Interface should be stripped"
assert "return null" not in result, "Null return should be replaced with launcher button"
assert "Launch Animated Feature" in result, "Launcher button should be rendered"
assert result.count("export default") == 1, "Should only have 1 export default"
assert "export { OtherComp };" in result, "Duplicate export default converted to named export"

print("\nALL ASSERTIONS PASSED! GUARDIAN IS WORKING PERFECTLY.")

# ================= PYTHON GUARDIAN TESTS =================
py_sample = """\
def check_rate_limit(client_ip: str) -> dict[str, Any]
\tcount = 1
\tfrom .rate_limiter import redis_cache
\treturn {"allowed": True, "ip": client_ip}
"""

py_result = guard_generated_code(py_sample, lang='py', file_path='app/rate_limiter.py')
print("\n=== PYTHON GUARDIAN OUTPUT ===")
print(py_result)

assert "\t" not in py_result, "Tabs should be replaced with spaces"
assert "from __future__ import annotations" in py_result, "Modern type annotations should inject future annotations"
assert "def check_rate_limit" in py_result and ":" in py_result, "Missing colon should be auto-repaired"
print("\nPYTHON GUARDIAN TESTS PASSED!")
