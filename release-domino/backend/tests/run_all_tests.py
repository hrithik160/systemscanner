#!/usr/bin/env python3
"""Unified test runner for Person 1 (LLM), Person 2 (Docker/Git), Person 3 (Graph/Risk), and Person 4 (React Flow UI)."""
import asyncio
import contextlib
import importlib.util
import inspect
import os
import sys
import types
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
for p in (str(BACKEND_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("RD_ALLOW_LOCAL_FALLBACK", "1")


def _install_pytest_shim_if_needed() -> None:
    if "pytest" in sys.modules:
        return
    try:
        import pytest  # noqa: F401
        return
    except ImportError:
        pass

    class _Mark:
        def __getattr__(self, _name: str):
            def _decorator(fn):
                return fn
            return _decorator

    @contextlib.contextmanager
    def _raises(exc_type):
        try:
            yield
        except exc_type:
            return
        raise AssertionError(f"Expected {exc_type} to be raised")

    def _fixture(*_a, **_kw):
        def _dec(fn):
            return fn
        if _a and callable(_a[0]):
            return _a[0]
        return _dec

    class _MonkeyPatch:
        def __init__(self):
            self._undo = []
        def setattr(self, target, name, value=None):
            old = getattr(target, name, None)
            self._undo.append((target, name, old))
            setattr(target, name, value)
        def setenv(self, k, v):
            os.environ[k] = str(v)
        def delenv(self, k, raising=False):
            os.environ.pop(k, None)
        def undo(self):
            for t, n, old in reversed(self._undo):
                setattr(t, n, old)

    shim = types.ModuleType("pytest")
    shim.mark = _Mark()
    shim.raises = _raises
    shim.fixture = _fixture
    shim.MonkeyPatch = _MonkeyPatch
    sys.modules["pytest"] = shim


def main() -> int:
    _install_pytest_shim_if_needed()
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.discover(str(TESTS_DIR), pattern="test_p2.py"))
    suite.addTests(loader.discover(str(TESTS_DIR), pattern="test_p3.py"))
    suite.addTests(loader.discover(str(TESTS_DIR), pattern="test_p3_p4_integration.py"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
