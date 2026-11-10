"""
Standalone Release Domino Web Wrapper with PEP 669 sys.monitoring (Python 3.12+)
and sys.setprofile fallback for Python <= 3.11.
"""
from __future__ import annotations

import os
import runpy
import sys
import time

_ws_abs_root = os.path.abspath(os.environ.get("RD_WORKSPACE_ROOT", os.getcwd()))
_last_emitted_node: dict[str, float] = {}
_THROTTLE_SECONDS = 0.15  # Max ~6 pulses per file per second


def _emit_active_node(rel_path: str) -> None:
    if not rel_path or rel_path.startswith("..") or "_rd_web_wrapper" in rel_path or "site-packages" in rel_path or ".venv" in rel_path:
        return
    now = time.monotonic()
    if (now - _last_emitted_node.get(rel_path, 0.0)) >= _THROTTLE_SECONDS:
        _last_emitted_node[rel_path] = now
        try:
            sys.stdout.write(f"[ACTIVE_NODE] {rel_path}\n")
            sys.stdout.flush()
        except Exception:
            pass


if sys.version_info >= (3, 12) and hasattr(sys, "monitoring"):
    # Python 3.12 / 3.14+ low-overhead PEP 669 monitoring
    _TOOL_ID = sys.monitoring.PROFILER_ID
    try:
        sys.monitoring.use_tool_id(_TOOL_ID, "rd_active_node_tracer")

        def _on_py_start(code, instruction_offset):
            co_f = os.path.abspath(code.co_filename)
            if co_f.startswith(_ws_abs_root):
                rel_f = os.path.relpath(co_f, _ws_abs_root).replace("\\", "/")
                _emit_active_node(rel_f)

        sys.monitoring.register_callback(
            _TOOL_ID,
            sys.monitoring.events.PY_START,
            _on_py_start,
        )
        sys.monitoring.set_events(_TOOL_ID, sys.monitoring.events.PY_START)
    except Exception:
        pass
else:
    # Legacy fallback for Python <= 3.11
    def _rd_profile_tracer(frame, event, arg):
        if event == "call":
            try:
                co_f = os.path.abspath(frame.f_code.co_filename)
                if co_f.startswith(_ws_abs_root):
                    rel_f = os.path.relpath(co_f, _ws_abs_root).replace("\\", "/")
                    _emit_active_node(rel_f)
            except Exception:
                pass

    sys.setprofile(_rd_profile_tracer)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
        sys.argv = sys.argv[1:]
        abs_target = os.path.abspath(target)
        target_dir = os.path.dirname(abs_target)
        if target_dir and target_dir not in sys.path:
            sys.path.insert(0, target_dir)
        try:
            runpy.run_path(target, run_name="__main__")
        except ImportError as e:
            if "attempted relative import with no known parent package" in str(e):
                import re
                try:
                    src = open(abs_target, "r", encoding="utf-8", errors="ignore").read()
                    healed = re.sub(r"\bfrom\s+\.([a-zA-Z0-9_]+)\s+import\b", r"from \1 import", src)
                    if healed != src:
                        code_obj = compile(healed, abs_target, "exec")
                        globs = {"__name__": "__main__", "__file__": abs_target}
                        exec(code_obj, globs)
                    else:
                        raise
                except Exception:
                    raise
            else:
                raise
