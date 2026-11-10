import React, { useEffect, useState } from 'react';
import {
  Activity,
  AudioWaveform,
  Boxes,
  Command,
  Crosshair,
  Gauge,
  GitBranch,
  Radio,
  Shield,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Wifi,
  WifiOff,
  Eye,
  X,
  AlertTriangle,
  Info,
  CheckCircle2,
} from 'lucide-react';
import { socketClient } from './store/socket';
import { useGraphStore } from './store/graphStore';
import { TopologyCanvas } from './components/TopologyCanvas';
import { CyberWorld3D } from './components/CyberWorld3D';
import { SimulationControlBar } from './components/SimulationControlBar';
import { DefenseToolbar } from './components/DefenseToolbar';
import { Hud } from './components/Hud';
import { NodeInspector } from './components/NodeInspector';
import { EdgeInspector } from './components/EdgeInspector';
import { Scorecard } from './components/Scorecard';

export function App() {
  const [scorecardOpen, setScorecardOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'3d' | '2d'>('3d');
  const {
    mode,
    setMode,
    connected,
    liveGraph,
    sim,
    activeToast,
    clearToast,
    simPlayback,
    startSimulation,
    pauseSimulation,
    resumeSimulation,
    resetSimulation,
  } = useGraphStore();

  useEffect(() => {
    socketClient.connect('ws://localhost:8000/ws');
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key.toLowerCase() === 'w') {
        setMode(mode === 'live' ? 'whatif' : 'live');
      } else if (e.key.toLowerCase() === 'r') {
        resetSimulation();
      } else if (e.key.toLowerCase() === 's') {
        setScorecardOpen((prev) => !prev);
      } else if (e.key.toLowerCase() === 'v') {
        setViewMode((prev) => (prev === '3d' ? '2d' : '3d'));
      } else if (e.code === 'Space') {
        e.preventDefault();
        if (simPlayback.status === 'running') {
          pauseSimulation();
        } else if (simPlayback.status === 'paused') {
          resumeSimulation();
        } else {
          startSimulation();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mode, setMode, simPlayback.status, startSimulation, pauseSimulation, resumeSimulation, resetSimulation]);

  const risk = sim.reachedCrownJewel ? 'CRITICAL' : sim.trappedByDecoy ? 'CONTAINED' : sim.blastRadius.compromised > 0 ? 'ELEVATED' : 'GUARDED';
  const riskTone = risk === 'CRITICAL' ? 'critical' : risk === 'CONTAINED' ? 'contained' : risk === 'ELEVATED' ? 'elevated' : 'guarded';

  return (
    <main className="command-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      {/* Floating Defense Toast Alert Notification */}
      {activeToast && (
        <div className="fixed top-24 left-1/2 -translate-x-1/2 z-50 animate-in fade-in zoom-in duration-300">
          <div
            className={`px-5 py-3 rounded-2xl border backdrop-blur-xl shadow-2xl flex items-center gap-3.5 max-w-md ${
              activeToast.type === 'success'
                ? 'bg-emerald-950/90 border-emerald-400 text-emerald-200 shadow-[0_0_30px_rgba(16,185,129,0.4)]'
                : activeToast.type === 'danger'
                ? 'bg-red-950/90 border-red-500 text-red-200 shadow-[0_0_30px_rgba(239,68,68,0.4)]'
                : activeToast.type === 'warning'
                ? 'bg-amber-950/90 border-amber-400 text-amber-200 shadow-[0_0_30px_rgba(251,191,36,0.4)]'
                : 'bg-[#1b1035]/95 border-[#8b5cf6] text-[#e9d5ff] shadow-[0_0_30px_rgba(139,92,246,0.4)]'
            }`}
          >
            <div className="p-1.5 rounded-lg bg-black/40">
              {activeToast.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              ) : activeToast.type === 'warning' || activeToast.type === 'danger' ? (
                <AlertTriangle className="w-5 h-5 text-amber-400" />
              ) : (
                <Info className="w-5 h-5 text-[#c084fc]" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] font-mono font-bold uppercase tracking-wider">
                {activeToast.title}
              </div>
              <div className="text-xs text-slate-300 mt-0.5 font-sans leading-tight">
                {activeToast.message}
              </div>
            </div>
            <button
              onClick={clearToast}
              className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Left Navigation Rail */}
      <aside className="side-rail">
        <div className="brand-mark">
          <Shield size={20} strokeWidth={2.4} />
          <span>RD</span>
        </div>
        <div className="rail-divider" />
        <button
          className={`rail-action ${viewMode === '3d' ? 'active' : ''}`}
          title="3D Cyber Warfare Space (Hotkey: V)"
          onClick={() => setViewMode('3d')}
        >
          <Boxes size={18} />
        </button>
        <button
          className={`rail-action ${viewMode === '2d' ? 'active' : ''}`}
          title="2D Schematic Graph (Hotkey: V)"
          onClick={() => setViewMode('2d')}
        >
          <GitBranch size={18} />
        </button>
        <button className="rail-action" title="Telemetry"><Activity size={18} /></button>
        <button className="rail-action" title="Command Center"><Gauge size={18} /></button>
        <div className="rail-spacer" />
        <button
          className={`rail-action ${mode === 'whatif' ? 'active text-amber-300' : ''}`}
          title="Toggle What-If Lab (Hotkey: W)"
          onClick={() => setMode(mode === 'live' ? 'whatif' : 'live')}
        >
          <Crosshair size={18} />
        </button>
        <div className="rail-avatar">RD</div>
      </aside>

      {/* Main Workspace Area */}
      <section className="workspace">
        <header className="topbar">
          <div className="topbar-project">
            <div className="project-glyph"><AudioWaveform size={18} /></div>
            <div>
              <div className="eyebrow">SECURITY OPERATIONS // SIMULATOR</div>
              <div className="project-name">
                RELEASE <span>DOMINO</span>
                <span className="project-env">{mode.toUpperCase()}</span>
              </div>
            </div>
          </div>
          <div className="topbar-center">
            <span className="breadcrumb-muted">Command</span>
            <span className="crumb-slash">/</span>
            <strong>Attack Surface Topology</strong>
            <span className="live-chip">
              <i /> {viewMode === '3d' ? '3D IMMERSIVE' : '2D TOPOLOGY'}
            </span>
          </div>
          <div className="topbar-right">
            <button
              onClick={() => setViewMode(viewMode === '3d' ? '2d' : '3d')}
              className="icon-button"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 12px',
                width: 'auto',
                background: viewMode === '3d' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(30, 20, 50, 0.6)',
                border: viewMode === '3d' ? '1px solid #8b5cf6' : '1px solid #4c1d95',
                color: viewMode === '3d' ? '#c084fc' : '#94a3b8',
                borderRadius: '9px',
                fontSize: '11px',
                fontWeight: 'bold',
                cursor: 'pointer',
              }}
              title="Toggle 3D Cyberspace / 2D Schematic (Hotkey: V)"
            >
              <Eye size={13} />
              <span>{viewMode === '3d' ? 'SWITCH TO 2D' : 'SWITCH TO 3D'}</span>
            </button>
            <div className={`connection-pill ${connected ? 'online' : 'offline'}`}>
              {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
              <span>{connected ? 'TELEMETRY LIVE' : 'DEMO MODE'}</span>
            </div>
            <div className="topbar-divider" />
            <button className="icon-button" title="Command shortcuts"><Command size={15} /></button>
            <div className="user-chip">RD</div>
          </div>
        </header>

        {/* Page Heading & Risk Badge */}
        <div className="page-heading">
          <div>
            <div className="heading-eyebrow">
              <Sparkles size={12} />
              <span>REAL-TIME ATTACK PATH INTELLIGENCE</span>
            </div>
            <h1>
              Infrastructure <em>Command Center</em>
            </h1>
            <p>Interactive 3D cyber simulation. Sever connections, remediate CVEs, and deflect attack chains.</p>
          </div>
          <div className="heading-meta">
            <div className="meta-label">SECURITY POSTURE</div>
            <div className={`risk-status ${riskTone}`}>
              <span className="risk-pulse" />
              {risk}
            </div>
            <div className="meta-foot">
              {mode === 'whatif' ? 'Remediation sandbox active' : 'Live production telemetry'}
            </div>
          </div>
        </div>

        {/* Metric Telemetry Strip */}
        <div className="metric-strip">
          <div className="metric-card">
            <div className="metric-icon red"><Crosshair size={16} /></div>
            <div className="metric-copy">
              <span>BLAST RADIUS</span>
              <strong>{sim.blastRadius.compromised}<small> / {sim.blastRadius.total}</small></strong>
            </div>
            <div className="metric-trend">ASSETS</div>
          </div>
          <div className="metric-card">
            <div className="metric-icon amber"><ShieldCheck size={16} /></div>
            <div className="metric-copy">
              <span>CROWN JEWEL</span>
              <strong className="metric-word">
                {sim.reachedCrownJewel ? 'EXPOSED' : sim.trappedByDecoy ? 'CONTAINED' : 'PROTECTED'}
              </strong>
            </div>
            <div className="metric-trend">TARGET</div>
          </div>
          <div className="metric-card">
            <div className="metric-icon mint"><Activity size={16} /></div>
            <div className="metric-copy">
              <span>TIME TO IMPACT</span>
              <strong>{sim.timeToCrownSec !== null ? `${sim.timeToCrownSec}<small> SEC</small>` : 'BLOCKED'}</strong>
            </div>
            <div className="metric-trend">ESTIMATE</div>
          </div>
          <div className="metric-card">
            <div className="metric-icon violet"><Boxes size={16} /></div>
            <div className="metric-copy">
              <span>ACTIVE ASSETS</span>
              <strong>{liveGraph.nodes.length.toString().padStart(2, '0')}<small> NODES</small></strong>
            </div>
            <div className="metric-trend">IN SCOPE</div>
          </div>
        </div>

        {/* Center Graph Section */}
        <section className="graph-section">
          {/* Top Line Header with 3D/2D Mode */}
          <div className="graph-topline">
            <div className="graph-title">
              <span className="graph-live-dot" />
              <div>
                <strong>Infrastructure Topology ({viewMode.toUpperCase()})</strong>
                <small>Connected graph • {liveGraph.edges.length} network pathways</small>
              </div>
            </div>
            <div className="graph-legend">
              <span><i className="legend-dot compromised" /> Compromised</span>
              <span><i className="legend-dot secure" /> Secure</span>
              <span><i className="legend-dot crown" /> Crown Jewel</span>
            </div>
            <div className="graph-tools">
              <button
                onClick={() => setViewMode(viewMode === '3d' ? '2d' : '3d')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '3px 9px',
                  borderRadius: '7px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid ' + (viewMode === '3d' ? '#8b5cf6' : '#4c1d95'),
                  background: viewMode === '3d' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(20, 10, 35, 0.6)',
                  color: viewMode === '3d' ? '#c084fc' : '#94a3b8',
                }}
              >
                <Boxes size={12} />
                <span>{viewMode === '3d' ? '3D VIEW' : '2D VIEW'}</span>
              </button>
              <span className="zoom-hint">
                {viewMode === '3d' ? 'LEFT DRAG ORBIT • RIGHT DRAG PAN • SCROLL ZOOM' : 'SCROLL TO ZOOM'}
              </span>
              <span className="graph-mode">
                {mode === 'live' ? <><Radio size={11} /> LIVE</> : <><Crosshair size={11} /> WHAT-IF</>}
              </span>
            </div>
          </div>

          {/* Integrated Simulation Playback & Progress Controller */}
          <SimulationControlBar />

          <div className="graph-stage">
            <div className="graph-vignette" />
            <div className="graph-watermark">RELEASE DOMINO // 3D CYBER WARFARE</div>
            {viewMode === '3d' ? <CyberWorld3D /> : <TopologyCanvas />}
          </div>

          <div className="graph-footer">
            <span>
              <span className="footer-pulse" />
              {viewMode === '3d' ? '3D R3F SHADER ENGINE' : '2D REACT FLOW SCHEMATIC'} ACTIVE
            </span>
            <span>SPACE: RUN/PAUSE • R: RESET • W: WHAT-IF • V: 3D/2D</span>
            <span className="footer-right">
              <TerminalSquare size={12} /> ATTACK SIMULATION ONLINE
            </span>
          </div>
        </section>
      </section>

      {/* Floating Overlays */}
      <DefenseToolbar onOpenScorecard={() => setScorecardOpen(true)} />
      <Hud />
      <NodeInspector />
      <EdgeInspector />
      <Scorecard open={scorecardOpen} onClose={() => setScorecardOpen(false)} />
    </main>
  );
}

export default App;
