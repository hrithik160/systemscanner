import React from 'react';
import {
  FolderOpen,
  Play,
  PlusCircle,
  Terminal,
  BarChart3,
  Download,
  FlaskRound,
  Cpu,
  Sparkles,
  Boxes,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const ReleaseToolbar: React.FC = () => {
  const {
    projectId,
    projects,
    connected,
    useMockMode,
    setIsOpenProjectModalOpen,
    setIsSandboxNodeModalOpen,
    setIsScorecardModalOpen,
    isTerminalOpen,
    setIsTerminalOpen,
    runTests,
    isRunningTests,
    fetchInitialWorkspace,
    triggerDockerRunWithShockwave,
    llmStatus,
    dockerStatus,
    toggleViewMode,
    setIsAiInspectorOpen,
  } = useReleaseStore();

  const handleDownloadReport = () => {
    window.open(`/api/report/${encodeURIComponent(projectId)}?format=md`, '_blank');
  };

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-30 flex items-center justify-center max-w-[96vw]">
      <div className="flex items-center gap-3 px-5 py-2.5 rounded-2xl bg-slate-900/95 border border-slate-700/90 backdrop-blur-md shadow-2xl flex-wrap justify-center">
        {/* Live Connection & Engine Status */}
        <div className="flex items-center gap-2 pr-3 border-r border-slate-800">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              connected
                ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                : useMockMode
                ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24]'
                : 'bg-sky-400'
            }`}
          />
          <span className="text-xs font-bold tracking-wide text-slate-200">
            RELEASE DOMINO
          </span>
          {llmStatus && (
            <button
              type="button"
              onClick={() => setIsAiInspectorOpen(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-mono bg-purple-950/80 border border-purple-500/50 text-purple-200 hover:bg-purple-900/90 hover:border-purple-400 transition cursor-pointer shadow-sm"
              title="Click to inspect Active AI Engine, ping test, and model settings"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
              <Sparkles className="w-3 h-3 text-purple-400" />
              <span className="font-semibold">{llmStatus.configured_model || 'NVIDIA NIM'}</span>
            </button>
          )}
          {dockerStatus && (
            <span
              className="hidden xl:inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-mono bg-emerald-950/70 border border-emerald-500/40 text-emerald-300"
              title="Person 2 Docker Sandbox Status"
            >
              <Cpu className="w-3 h-3" />
              {dockerStatus.docker_available ? 'Docker Ready' : 'Sandbox Ready'}
            </span>
          )}
        </div>

        {/* Active Project Selector & Open Repo Button */}
        <div className="flex items-center gap-2 pr-3 border-r border-slate-800">
          <select
            value={projectId}
            onChange={(e) => fetchInitialWorkspace(e.target.value)}
            aria-label="Select Active Project"
            className="rounded-xl bg-slate-950 border border-slate-700 px-3 py-1.5 text-xs font-mono text-sky-300 focus:outline-none focus:border-sky-500 max-w-[200px] truncate"
          >
            {projects.map((p) => {
              const id = p.project_id || (p as any).pid || "";
              return (
                <option key={id} value={id}>
                  {p.name || id} ({p.runtime || (p as any).stack || "py"})
                </option>
              );
            })}
          </select>

          <button
            onClick={() => setIsOpenProjectModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-100 text-xs font-semibold transition shadow"
            title="Open local project folder or clone GitHub repository (Shortcut: O)"
          >
            <FolderOpen className="w-4 h-4 text-sky-400" /> Open Project
          </button>
        </div>

        {/* Primary Action: Run Project in Docker (Automatically triggers Shockwave!) */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => triggerDockerRunWithShockwave()}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-lg shadow-emerald-950/50"
            title="Run project inside Docker container and animate live dependency shockwave"
          >
            <Play className="w-4 h-4 fill-current" /> Run in Docker
          </button>

          <button
            onClick={() => runTests(false)}
            disabled={isRunningTests}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-sky-600/30 border border-sky-500/50 text-sky-100 hover:bg-sky-600/50 transition shadow disabled:opacity-50"
            title="Run automated tests + coverage in Docker and animate shockwave"
          >
            <FlaskRound className={`w-4 h-4 text-sky-400 ${isRunningTests ? 'animate-spin' : ''}`} />
            {isRunningTests ? 'Testing...' : 'Run Tests'}
          </button>

          <button
            onClick={() => setIsSandboxNodeModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-100 hover:bg-slate-700 transition"
            title="Paste code to add a Sandbox node to the graph"
          >
            <PlusCircle className="w-4 h-4 text-emerald-400" /> Add Node
          </button>

          <button
            onClick={toggleViewMode}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-purple-950/70 border border-purple-500/50 text-purple-200 hover:bg-purple-900/80 transition shadow cursor-pointer"
            title="Toggle 3D Immersive Cyber Warfare Topology (Shortcut: V)"
          >
            <Boxes className="w-4 h-4 text-purple-400" /> 3D View
          </button>

          <button
            onClick={() => setIsTerminalOpen(!isTerminalOpen)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
              isTerminalOpen
                ? 'bg-emerald-500/25 border-emerald-400 text-emerald-200'
                : 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
            }`}
            title="Toggle Docker Container Terminal Drawer (Shortcut: T)"
          >
            <Terminal className="w-4 h-4 text-emerald-400" /> Terminal
          </button>

          <button
            onClick={() => setIsScorecardModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow"
            title="Open Release Scorecard & Branch Comparison View (Shortcut: S)"
          >
            <BarChart3 className="w-4 h-4" /> Scorecard
          </button>

          <button
            onClick={handleDownloadReport}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100"
            title="Download Markdown Release Report"
          >
            <Download className="w-4 h-4 text-sky-400" /> Report
          </button>
        </div>
      </div>
    </div>
  );
};
