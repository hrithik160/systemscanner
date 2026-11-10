import React, { useState, useEffect, useRef } from 'react';
import {
  Terminal,
  Play,
  Square,
  FlaskRound,
  Package,
  Trash2,
  ChevronDown,
  ExternalLink,
  Send,
  Wand2,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

interface TermLine {
  stream: 'stdout' | 'stderr' | 'system';
  data: string;
  ts: number;
}

const SHELL_CMD_PREFIXES = new Set([
  'pytest', 'python', 'python3', 'ls', 'cat', 'flake8', 'ruff',
  'jest', 'npm', 'npx', 'node', 'uname', 'id', 'pwd', 'uvicorn',
  'flask', 'django-admin', 'run', 'test', 'install', 'stop', 'kill',
]);

export const DockerTerminalDrawer: React.FC = () => {
  const {
    projectId,
    isTerminalOpen,
    setIsTerminalOpen,
    fetchInitialWorkspace,
    startShockwave,
    dockerAutoRunCounter,
    isProgramRunning,
    startExecutionTrace,
    setExecutingNode,
    stopExecutionTrace,
  } = useReleaseStore() as any;

  const [lines, setLines] = useState<TermLine[]>([]);
  const [inputVal, setInputVal] = useState('');
  const [waitingForInput, setWaitingForInput] = useState(false);
  const [livePreviewUrl, setLivePreviewUrl] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [isRepairing, setIsRepairing] = useState(false);
  const [repairMsg, setRepairMsg] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const lastRunCounterRef = useRef<number>(0);

  const detectedRuntimeError = lines.slice(-40).map((l) => l.data).join('\n');
  const hasImportOrModuleError = /Failed to resolve import|Cannot find module|ModuleNotFoundError|SyntaxError|does the file exist\?/i.test(detectedRuntimeError);

  const handleAutoRepairError = async () => {
    setIsRepairing(true);
    setRepairMsg(null);
    try {
      const recentLogs = lines.slice(-60).map((l) => l.data).join('\n');
      const res = await fetch('/api/sandbox/auto-fix-runtime-error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, error_log: recentLogs }),
      });
      const data = await res.json();
      if (data.repaired) {
        setRepairMsg(`✅ ${data.message} (${(data.actions || []).length} action(s) taken)`);
        fetchInitialWorkspace(projectId);
        sendCommand({ cmd: 'run' });
      } else {
        setRepairMsg(`⚠️ ${data.message || 'Could not automatically repair error'}`);
      }
    } catch (err: any) {
      setRepairMsg(`❌ Auto-repair error: ${err.message || 'Unknown network error'}`);
    } finally {
      setIsRepairing(false);
    }
  };

  const sendCommand = (payload: Record<string, unknown>) => {
    if (payload.cmd === 'run' || payload.cmd === 'test') {
      startShockwave(1);
      if (startExecutionTrace) startExecutionTrace();
    } else if (payload.cmd === 'stop') {
      if (stopExecutionTrace) stopExecutionTrace();
      setWaitingForInput(false);
    }
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          strict_docker: false,
          force_local: true,
          keep_alive_sec: 15,
          allow_network: true,
          ...payload,
        })
      );
    } else {
      setLines((prev) => [
        ...prev,
        {
          stream: 'system',
          data: `[Local Sandbox] Launching '${payload.cmd || payload.stdin}' for project '${projectId}'...\n`,
          ts: Date.now(),
        },
      ]);
    }
  };

  useEffect(() => {
    if (!isTerminalOpen) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host || '127.0.0.1:8000';
    const ws = new WebSocket(`${proto}://${host}/ws/terminal/${encodeURIComponent(projectId)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      if (dockerAutoRunCounter > lastRunCounterRef.current) {
        lastRunCounterRef.current = dockerAutoRunCounter;
        if (startExecutionTrace) startExecutionTrace();
        ws.send(
          JSON.stringify({
            cmd: 'run',
            strict_docker: false,
            force_local: true,
            keep_alive_sec: 15,
            allow_network: true,
          })
        );
      }
    };

    ws.onmessage = (evt) => {
      try {
        const msg: TermLine = JSON.parse(evt.data);
        if (msg.data) {
          // Check for active node trace markers
          const nodeMatches = Array.from(msg.data.matchAll(/\[ACTIVE_NODE\]\s*([^\r\n]+)/g));
          for (const m of nodeMatches) {
            if (m[1] && setExecutingNode) {
              setExecutingNode(m[1].trim());
            }
          }
          if (msg.data.includes('[WAITING_FOR_INPUT]')) {
            setWaitingForInput(true);
          }
          const urlMatch = msg.data.match(/\[LIVE_PREVIEW_URL\]\s*(https?:\/\/[^\s]+)/);
          if (urlMatch) {
            setLivePreviewUrl(urlMatch[1]);
          }
          if (msg.data.includes('[Process exited') || msg.data.includes('Docker Container Stopped')) {
            setWaitingForInput(false);
            if (stopExecutionTrace) stopExecutionTrace();
          }
          if (
            msg.data.includes('test_run_finished') ||
            msg.data.includes('passed') ||
            msg.data.includes('Launching entrypoint') ||
            msg.data.includes('Project is running live') ||
            msg.data.includes('running live at') ||
            msg.data.includes('Detected architecture') ||
            msg.data.includes('[RunPlan Engine]') ||
            msg.data.includes('[Process started')
          ) {
            startShockwave(1);
            if (startExecutionTrace) startExecutionTrace();
            fetchInitialWorkspace(projectId);
          }
          // Strip internal [ACTIVE_NODE] and [WAITING_FOR_INPUT] tags from visible terminal output if clean
          const cleaned = msg.data
            .replace(/\[ACTIVE_NODE\]\s*[^\r\n]+\r?\n?/g, '')
            .replace(/\[WAITING_FOR_INPUT\]\r?\n?/g, '');
          if (!cleaned) return;
          msg.data = cleaned;
        }
        setLines((prev) => [...prev.slice(-300), msg]);
      } catch {
        setLines((prev) => [
          ...prev.slice(-300),
          { stream: 'stdout', data: String(evt.data), ts: Date.now() },
        ]);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [isTerminalOpen, projectId, fetchInitialWorkspace, startShockwave]);

  useEffect(() => {
    if (
      isTerminalOpen &&
      dockerAutoRunCounter > lastRunCounterRef.current &&
      wsRef.current &&
      wsRef.current.readyState === WebSocket.OPEN
    ) {
      lastRunCounterRef.current = dockerAutoRunCounter;
      sendCommand({ cmd: 'run' });
    }
  }, [dockerAutoRunCounter, isTerminalOpen]);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [lines]);

  if (!isTerminalOpen) return null;

  const isStdinMode = Boolean(waitingForInput || isProgramRunning);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 h-96 max-h-[65vh] bg-slate-950/95 border-t border-slate-700/90 backdrop-blur-md shadow-2xl flex flex-col">
      <div className="flex items-center justify-between px-5 py-2.5 bg-slate-900/95 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-2 font-bold text-slate-100">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Local Isolated Sandbox Terminal (Interactive CLI + Web)</span>
            <span className="px-2 py-0.5 rounded-md bg-slate-800 text-sky-300 font-mono text-[11px]">
              /ws/terminal/{projectId}
            </span>
          </div>
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              wsConnected ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-amber-400'
            }`}
          />
          {waitingForInput && (
            <span className="px-2.5 py-0.5 rounded-full bg-blue-500/30 border border-blue-400 text-blue-200 font-mono text-[11px] font-bold animate-pulse">
              ⌨️ Waiting for your input below
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {hasImportOrModuleError && (
            <button
              onClick={handleAutoRepairError}
              disabled={isRepairing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-400 via-rose-500 to-indigo-500 hover:opacity-95 text-slate-950 font-extrabold text-xs shadow-lg animate-pulse transition"
              title="AI will analyze project exports, repair broken imports, and restart the sandbox"
            >
              {isRepairing ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-slate-950" />
              ) : (
                <Wand2 className="w-3.5 h-3.5 fill-current text-slate-950" />
              )}
              <span>⚡ Fix Runtime Error with AI</span>
            </button>
          )}

          <button
            onClick={() => sendCommand({ cmd: 'run' })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow transition"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Run Project (Local Sandbox)
          </button>

          {livePreviewUrl && (
            <div className="flex items-center gap-1.5">
              <a
                href={livePreviewUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold text-xs shadow"
              >
                <ExternalLink className="w-3.5 h-3.5" /> Open Live App ({livePreviewUrl})
              </a>
              <a
                href={`${livePreviewUrl.replace(/\/$/, '')}/docs`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-emerald-500/20 border border-emerald-500/50 hover:bg-emerald-500/30 text-emerald-300 font-bold text-xs"
                title="Open FastAPI / Swagger API Docs"
              >
                <ExternalLink className="w-3 h-3" /> /docs
              </a>
            </div>
          )}

          <button
            onClick={() => sendCommand({ cmd: 'test' })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-600/30 border border-sky-500/50 hover:bg-sky-600/50 text-sky-100 font-semibold text-xs transition"
          >
            <FlaskRound className="w-3.5 h-3.5" /> Run Tests + Coverage
          </button>

          <button
            onClick={() => sendCommand({ cmd: 'install' })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs"
          >
            <Package className="w-3.5 h-3.5 text-amber-400" /> Install Deps
          </button>

          <button
            onClick={() => sendCommand({ cmd: 'stop' })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-600/30 border border-red-500/50 hover:bg-red-600/50 text-red-200 font-semibold text-xs"
          >
            <Square className="w-3.5 h-3.5 fill-current" /> Stop
          </button>

          <button
            onClick={() => setLines([])}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs"
          >
            <Trash2 className="w-3.5 h-3.5" /> Clear
          </button>

          <button
            onClick={() => setIsTerminalOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            title="Minimize Terminal Drawer"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {repairMsg && (
        <div className="flex items-center justify-between px-5 py-2 bg-indigo-950/90 border-b border-indigo-700/60 text-xs text-indigo-100 shadow-md">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="font-semibold">{repairMsg}</span>
          </div>
          <button
            onClick={() => setRepairMsg(null)}
            className="text-slate-300 hover:text-white px-2 py-0.5 rounded bg-slate-800 text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      <div ref={logContainerRef} className="flex-1 overflow-y-auto px-5 py-3 font-mono text-xs space-y-1 bg-[#05080f]">
        {lines.length === 0 ? (
          <div className="text-slate-400 py-4">
            Ready. Click &quot;Run Project (Local Sandbox)&quot; to run web apps or interactive CLI terminal programs (nodes glow blue as they execute)...
          </div>
        ) : (
          lines.map((ln, idx) => (
            <div
              key={idx}
              className={`whitespace-pre-wrap break-all leading-relaxed ${
                ln.stream === 'stderr'
                  ? 'text-rose-400'
                  : ln.stream === 'system'
                  ? 'text-sky-400 font-semibold'
                  : 'text-slate-200'
              }`}
            >
              {ln.data}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const trimmed = inputVal.trim();
          if (!trimmed && !waitingForInput) return;
          const firstTok = trimmed.split(/\s+/)[0] || '';
          if (waitingForInput || (isProgramRunning && !SHELL_CMD_PREFIXES.has(firstTok))) {
            sendCommand({ stdin: inputVal });
            setWaitingForInput(false);
          } else {
            sendCommand({ cmd: trimmed });
          }
          setInputVal('');
        }}
        className={`flex items-center gap-2 px-5 py-2 border-t text-xs font-mono transition ${
          waitingForInput
            ? 'bg-blue-950/60 border-blue-500/70'
            : 'bg-slate-900 border-slate-800'
        }`}
      >
        <span className={`font-bold ${isStdinMode ? 'text-blue-400' : 'text-emerald-400'}`}>
          {isStdinMode ? 'stdin@running-app:>' : 'sandbox@rd-local:$'}
        </span>
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder={
            isStdinMode
              ? 'Type interactive input for running program and press Enter (or type stop / pytest -q)...'
              : 'Type interactive program input or command (pytest -q, python main.py, npm test)...'
          }
          className="flex-1 bg-transparent text-slate-100 focus:outline-none"
        />
        <button
          type="submit"
          className={`px-3 py-1 rounded-lg flex items-center gap-1 text-xs font-semibold ${
            isStdinMode
              ? 'bg-blue-600 hover:bg-blue-500 text-white shadow'
              : 'bg-slate-800 hover:bg-slate-700 text-sky-300'
          }`}
        >
          <Send className="w-3.5 h-3.5" /> {isStdinMode ? 'Send Input' : 'Run'}
        </button>
      </form>
    </div>
  );
};
