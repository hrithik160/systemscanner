"""
Task D8 — Debounced Project File Watcher (backend/app/git_ops/watcher.py)
Monitors a project directory using `watchdog` (with a 500 ms debounce window),
ignoring `.git/`, `node_modules/`, `.venv/`, and `__pycache__/`. On file change,
recomputes diff, emits `file_changed` and `diff_updated`, and triggers P3's re-analysis callback.
"""
import asyncio
import logging
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Callable, Awaitable, Dict, List, Optional, Set

from app.git_ops.diff import compute_diff

logger = logging.getLogger("release_domino.git_ops.watcher")

IGNORED_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
IGNORED_FILES = {".coverage", "rd_coverage_out.json", "rd_jest_out.json"}


class DebouncedRepoWatcher:
    def __init__(
        self,
        project_id: str,
        repo_path: Path,
        emit_event: Callable[[str, str, dict], Awaitable[None]],
        on_reanalyze: Optional[Callable[[str, List[str]], Awaitable[None]]] = None,
        debounce_sec: float = 0.5,
    ):
        self.project_id = project_id
        self.repo_path = repo_path.resolve()
        self.emit_event = emit_event
        self.on_reanalyze = on_reanalyze
        self.debounce_sec = debounce_sec
        self._pending_files: Set[str] = set()
        self._last_change_ts: float = 0.0
        self._observer = None
        self._flush_future: Optional[Future] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _is_ignored(self, path_str: str) -> bool:
        p = Path(path_str)
        if p.name in IGNORED_FILES or p.name.endswith((".pyc", ".tmp", ".swp")):
            return True
        return any(part in IGNORED_DIRS for part in p.parts)

    def notify_file_modified(self, abs_or_rel_path: str) -> None:
        """Records a modified file path and resets the 500ms debounce timer."""
        if self._is_ignored(abs_or_rel_path):
            return
        try:
            rel = str(Path(abs_or_rel_path).resolve().relative_to(self.repo_path)).replace("\\", "/")
        except Exception:
            rel = str(abs_or_rel_path).replace("\\", "/")
        if self._is_ignored(rel):
            return
        self._pending_files.add(rel)
        self._last_change_ts = time.monotonic()
        if self._loop and not self._loop.is_closed():
            if self._flush_future is None or self._flush_future.done():
                self._flush_future = asyncio.run_coroutine_threadsafe(
                    self._debounce_flush(), self._loop
                )

    async def _debounce_flush(self) -> None:
        while True:
            elapsed = time.monotonic() - self._last_change_ts
            remaining = self.debounce_sec - elapsed
            if remaining <= 0:
                break
            await asyncio.sleep(remaining)

        changed = sorted(self._pending_files)
        self._pending_files.clear()
        if not changed:
            return

        await self.emit_event("file_changed", self.project_id, {"files": changed})
        diff_res = await compute_diff(self.repo_path)
        await self.emit_event("diff_updated", self.project_id, diff_res.model_dump())

        if self.on_reanalyze:
            await self.on_reanalyze(self.project_id, changed)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
        self._loop = loop
        if self._observer is not None:
            return
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            watcher_self = self

            class _Handler(FileSystemEventHandler):
                def on_any_event(self, event):
                    if event.is_directory:
                        return
                    watcher_self.notify_file_modified(event.src_path)

            self._observer = Observer()
            self._observer.schedule(_Handler(), str(self.repo_path), recursive=True)
            self._observer.start()
            logger.info("Started watchdog file watcher on %s (500ms debounce)", self.repo_path)
        except ImportError:
            logger.warning("watchdog not installed; manual trigger mode active")

    def stop(self) -> None:
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None


class WatcherManager:
    """Manages active DebouncedRepoWatchers across opened projects."""

    def __init__(self) -> None:
        self._watchers: Dict[str, DebouncedRepoWatcher] = {}

    def start_watching(
        self,
        project_id: str,
        repo_path: Path,
        emit_event: Callable[[str, str, dict], Awaitable[None]],
        on_reanalyze: Optional[Callable[[str, List[str]], Awaitable[None]]] = None,
        debounce_sec: float = 0.5,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> DebouncedRepoWatcher:
        existing = self._watchers.get(project_id)
        if existing and existing.repo_path == repo_path.resolve():
            if existing._loop is None and loop is not None:
                existing._loop = loop
            return existing
        if existing:
            existing.stop()
        w = DebouncedRepoWatcher(
            project_id=project_id,
            repo_path=repo_path,
            emit_event=emit_event,
            on_reanalyze=on_reanalyze,
            debounce_sec=debounce_sec,
        )
        w.start(loop=loop)
        self._watchers[project_id] = w
        return w

    def stop_all(self) -> None:
        for w in list(self._watchers.values()):
            w.stop()
        self._watchers.clear()


watcher_manager = WatcherManager()
