import { useEffect } from 'react';
import { ReleaseCanvas } from './components/ReleaseCanvas';
import { ReleaseToolbar } from './components/ReleaseToolbar';
import { RiskHud } from './components/RiskHud';
import { NodeInspector } from './components/NodeInspector';
import { DockerTerminalDrawer } from './components/DockerTerminalDrawer';
import { OpenProjectModal } from './components/OpenProjectModal';
import { SandboxNodeModal } from './components/SandboxNodeModal';
import { ConnectDiffModal } from './components/ConnectDiffModal';
import { ReleaseScorecardModal } from './components/ReleaseScorecardModal';
import { NodeStudioModal } from './components/NodeStudioModal';
import { AiInspectorModal } from './components/AiInspectorModal';
import { useReleaseStore } from './store/releaseStore';
import { releaseSocket } from './store/socket';

export function App() {
  const {
    viewMode,
    toggleViewMode,
    mode,
    setMode,
    resetShockwave,
    fetchInitialWorkspace,
    setIsScorecardModalOpen,
    isTerminalOpen,
    setIsTerminalOpen,
    setIsOpenProjectModalOpen,
    errorBanner,
    setErrorBanner,
  } = useReleaseStore();

  useEffect(() => {
    releaseSocket.connect();
    fetchInitialWorkspace('demo');
    return () => {
      releaseSocket.disconnect();
    };
  }, [fetchInitialWorkspace]);

  // Demo Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      const key = e.key.toLowerCase();
      if (key === 'v') {
        toggleViewMode();
      } else if (key === 'w') {
        setMode(mode === 'live' ? 'whatif' : 'live');
      } else if (key === 'r') {
        resetShockwave();
        fetchInitialWorkspace();
      } else if (key === 's') {
        setIsScorecardModalOpen(true);
      } else if (key === 't') {
        setIsTerminalOpen(!isTerminalOpen);
      } else if (key === 'o') {
        setIsOpenProjectModalOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    toggleViewMode,
    mode,
    setMode,
    resetShockwave,
    fetchInitialWorkspace,
    setIsScorecardModalOpen,
    isTerminalOpen,
    setIsTerminalOpen,
    setIsOpenProjectModalOpen,
  ]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#060911] select-none">
      {/* 2D-only Floating Chrome */}
      {viewMode === '2d' && (
        <>
          <ReleaseToolbar />
          <RiskHud />
        </>
      )}

      {/* Main Interactive Dependency Graph Canvas (React Flow in 2D, CyberWorld3D in 3D) */}
      <ReleaseCanvas />

      {/* Right-Hand Tabbed Node Inspector (in 2D) */}
      {viewMode === '2d' && <NodeInspector />}

      {/* Bottom Collapsible Docker Terminal Drawer */}
      <DockerTerminalDrawer />

      {/* Modals */}
      <OpenProjectModal />
      <SandboxNodeModal />
      <ConnectDiffModal />
      <ReleaseScorecardModal />
      <NodeStudioModal />
      <AiInspectorModal />

      {/* Dismissible Notification Banner */}
      {errorBanner && (
        <div
          onClick={() => setErrorBanner(null)}
          className="fixed bottom-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full bg-amber-950/90 border border-amber-500/60 text-amber-200 text-xs font-mono shadow-xl cursor-pointer"
        >
          {errorBanner} (click to dismiss)
        </div>
      )}

      {/* Bottom-Left Legend & Keyboard Shortcut Pill (in 2D) */}
      {viewMode === '2d' && (
        <div className="fixed bottom-4 left-5 z-20 flex items-center gap-3 px-3.5 py-2 rounded-xl bg-slate-900/85 border border-slate-800 text-[11px] text-slate-400 backdrop-blur-sm">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" /> Normal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" /> Changed
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" /> Impacted Wave
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" /> Failing Test
          </span>
          <span className="border-l border-slate-700 pl-3 font-mono text-[10px]">
            [V] 3D/2D • [W] What-If • [R] Refresh • [S] Scorecard • [T] Terminal • [O] Open Repo
          </span>
        </div>
      )}
    </div>
  );
}

export default App;
