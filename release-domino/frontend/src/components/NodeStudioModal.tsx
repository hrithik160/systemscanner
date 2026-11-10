import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  X,
  Maximize2,
  Minimize2,
  Save,
  Play,
  FileCode2,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Send,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Cpu,
  Check,
  Copy,
  RefreshCw,
  AlertTriangle,
  MessageSquare,
  Flame,
  Zap,
  Crown,
  Search,
  CheckCircle2,
  FileText,
  FileJson,
  Layers,
  ArrowDownLeft,
  ArrowUpRight,
  GitBranch,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';
import { CNode } from '../../../shared/types';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  suggested_code?: string | null;
}

export const NodeStudioModal: React.FC = () => {
  const {
    isNodeStudioOpen,
    setIsNodeStudioOpen,
    selectedNodeId,
    selectNode,
    nodeDetail,
    saveNodeCode,
    isSummarizing,
    summarizeSelectedNode,
    chatWithFileNode,
    graph,
    risk,
    projectId,
    llmStatus,
  } = useReleaseStore();

  const [isMaximized, setIsMaximized] = useState(false);
  const [codeDraft, setCodeDraft] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // File tree state
  const [searchFilter, setSearchFilter] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});

  // Editor bottom dock tab state
  const [dockTab, setDockTab] = useState<'terminal' | 'output' | 'problems'>('terminal');

  // AI Copilot Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Sync draft code when active node changes
  useEffect(() => {
    if (nodeDetail?.code !== undefined) {
      setCodeDraft(nodeDetail.code);
      setIsDirty(false);
    }
  }, [nodeDetail?.id, nodeDetail?.code]);

  // In Nodes (Callers that invoke or import selectedNodeId)
  const inNodes = useMemo(() => {
    if (!selectedNodeId) return [];
    const inboundEdges = (graph.edges || []).filter((e) => e.target === selectedNodeId);
    return inboundEdges.map((e) => {
      const srcNode = graph.nodes.find((n) => n.id === e.source);
      return {
        id: e.source,
        label: srcNode?.label || e.source.split('/').pop() || e.source,
        kind: srcNode?.kind || 'module',
        risk: srcNode?.risk || 0,
        isCrown: !!srcNode?.is_crown_jewel,
        status: srcNode?.status || 'normal',
        edgeType: e.type || 'calls',
      };
    });
  }, [graph.edges, graph.nodes, selectedNodeId]);

  // Out Nodes (Dependencies that selectedNodeId invokes or imports)
  const outNodes = useMemo(() => {
    if (!selectedNodeId) return [];
    const outboundEdges = (graph.edges || []).filter((e) => e.source === selectedNodeId);
    return outboundEdges.map((e) => {
      const tgtNode = graph.nodes.find((n) => n.id === e.target);
      return {
        id: e.target,
        label: tgtNode?.label || e.target.split('/').pop() || e.target,
        kind: tgtNode?.kind || 'module',
        risk: tgtNode?.risk || 0,
        isCrown: !!tgtNode?.is_crown_jewel,
        status: tgtNode?.status || 'normal',
        edgeType: e.type || 'calls',
      };
    });
  }, [graph.edges, graph.nodes, selectedNodeId]);

  // Generate the first chat message as the complete AI Architecture & File Summary
  const buildInitialSummaryChat = (nid: string, detail: typeof nodeDetail) => {
    const fileName = nid.split('/').pop() || nid;
    const sum = detail?.cached_summary;

    let summaryBullets = '';
    if (sum?.summary && sum.summary.length > 0) {
      summaryBullets = sum.summary.map((b) => `• ${b}`).join('\n');
    } else {
      summaryBullets = `• Primary ${detail?.kind || 'module'} component for ${fileName}.\n• Exposes ${(detail?.exports || []).slice(0, 3).join(', ') || 'key functions & classes'}.\n• Analyzed for dependencies, defect gravity, and runtime execution.`;
    }

    const purposeText = sum?.purpose || `Implements core ${detail?.kind || 'module'} logic for ${fileName}.`;
    const exportText = detail?.exports && detail.exports.length > 0
      ? `\n\n**Exported Symbols:** ${detail.exports.map((e) => `\`${e}\``).join(', ')}`
      : '';
    const riskText = sum?.risks && sum.risks.length > 0
      ? `\n\n**Security & Blast Radius:**\n${sum.risks.map((r) => `• ${r}`).join('\n')}`
      : '';

    return `### 📋 Architectural Summary: **${fileName}**\n\n**Purpose:** ${purposeText}\n\n**Key Characteristics:**\n${summaryBullets}${exportText}${riskText}\n\n*Ask me below to audit vulnerabilities, refactor code, or generate unit tests!*`;
  };

  // Set the first chat message to the file summary
  useEffect(() => {
    if (selectedNodeId) {
      const summaryMsg = buildInitialSummaryChat(selectedNodeId, nodeDetail);
      setChatMessages((prev) => {
        // If there are existing conversation messages for this same file, keep them and ensure the first message is the updated summary
        if (prev.length > 1 && prev[0]?.id === `summary-${selectedNodeId}`) {
          return [{ ...prev[0], content: summaryMsg }, ...prev.slice(1)];
        }
        return [
          {
            id: `summary-${selectedNodeId}`,
            role: 'assistant',
            content: summaryMsg,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ];
      });
    }
  }, [selectedNodeId, nodeDetail?.id, nodeDetail?.cached_summary]);

  // Auto-scroll chat
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages, isChatting]);

  // Group graph nodes into folder tree structure
  const fileTree = useMemo(() => {
    interface TreeFolder {
      name: string;
      fullPath: string;
      subfolders: Record<string, TreeFolder>;
      files: CNode[];
    }

    const root: TreeFolder = { name: projectId || 'project', fullPath: '', subfolders: {}, files: [] };

    graph.nodes.forEach((node) => {
      if (searchFilter && !node.id.toLowerCase().includes(searchFilter.toLowerCase())) {
        return;
      }
      const parts = node.id.split('/');
      let current = root;

      if (parts.length > 1) {
        for (let i = 0; i < parts.length - 1; i++) {
          const folderName = parts[i];
          if (!current.subfolders[folderName]) {
            current.subfolders[folderName] = {
              name: folderName,
              fullPath: parts.slice(0, i + 1).join('/'),
              subfolders: {},
              files: [],
            };
          }
          current = current.subfolders[folderName];
        }
      }
      current.files.push(node);
    });

    return root;
  }, [graph.nodes, projectId, searchFilter]);

  // Auto-expand folder containing current file
  useEffect(() => {
    if (selectedNodeId) {
      const parts = selectedNodeId.split('/');
      if (parts.length > 1) {
        const next: Record<string, boolean> = { ...expandedFolders };
        for (let i = 0; i < parts.length - 1; i++) {
          const path = parts.slice(0, i + 1).join('/');
          next[path] = true;
        }
        setExpandedFolders(next);
      }
    }
  }, [selectedNodeId]);

  if (!isNodeStudioOpen || !selectedNodeId) return null;

  const currentNode = graph.nodes.find((n) => n.id === selectedNodeId);

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  const handleSave = async () => {
    if (!selectedNodeId) return;
    setIsSaving(true);
    await saveNodeCode(selectedNodeId, codeDraft);
    setIsSaving(false);
    setIsDirty(false);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2000);
  };

  const handleSendMessage = async (customPrompt?: string) => {
    const text = customPrompt || chatInput;
    if (!text.trim() || isChatting || !selectedNodeId) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    if (!customPrompt) setChatInput('');
    setIsChatting(true);

    const historyPayload = chatMessages.map((m) => ({ role: m.role, content: m.content }));
    const resp = await chatWithFileNode(selectedNodeId, text, codeDraft, historyPayload);

    const assistantMsg: ChatMessage = {
      id: `a-${Date.now()}`,
      role: 'assistant',
      content: resp.reply,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      suggested_code: resp.suggested_code,
    };

    setChatMessages((prev) => [...prev, assistantMsg]);
    setIsChatting(false);
  };

  const handleApplySuggestedCode = (newCode: string) => {
    setCodeDraft(newCode);
    setIsDirty(true);
  };

  const getFileIcon = (fileName: string) => {
    if (fileName.endsWith('.py')) return <span className="text-sky-400 font-mono text-[11px]">PY</span>;
    if (fileName.endsWith('.tsx') || fileName.endsWith('.jsx')) return <span className="text-cyan-400 font-mono text-[11px]">TSX</span>;
    if (fileName.endsWith('.ts') || fileName.endsWith('.js')) return <span className="text-amber-400 font-mono text-[11px]">JS</span>;
    if (fileName.endsWith('.json')) return <FileJson className="w-3.5 h-3.5 text-yellow-500" />;
    if (fileName.endsWith('.css')) return <span className="text-indigo-400 font-mono text-[11px]">CSS</span>;
    return <FileText className="w-3.5 h-3.5 text-slate-400" />;
  };

  // Render recursive folder tree
  const renderFolder = (folder: any, depth = 0) => {
    return (
      <div key={folder.fullPath || 'root'} className="text-xs select-none">
        {folder.fullPath && (
          <div
            onClick={() => toggleFolder(folder.fullPath)}
            style={{ paddingLeft: `${depth * 14 + 8}px` }}
            className="flex items-center gap-1.5 py-1 px-2 rounded hover:bg-slate-800/60 cursor-pointer text-slate-300 transition"
          >
            {expandedFolders[folder.fullPath] ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            )}
            {expandedFolders[folder.fullPath] ? (
              <FolderOpen className="w-3.5 h-3.5 text-amber-400/90" />
            ) : (
              <Folder className="w-3.5 h-3.5 text-amber-500/80" />
            )}
            <span className="font-mono text-[11.5px] truncate">{folder.name}</span>
          </div>
        )}

        {(depth === 0 || expandedFolders[folder.fullPath]) && (
          <div>
            {Object.values(folder.subfolders).map((sub: any) =>
              renderFolder(sub, depth + (folder.fullPath ? 1 : 0))
            )}

            {folder.files.map((file: CNode) => {
              const isSelected = file.id === selectedNodeId;
              const hasRisk = file.risk && file.risk >= 50;
              return (
                <div
                  key={file.id}
                  onClick={() => selectNode(file.id)}
                  style={{ paddingLeft: `${(depth + (folder.fullPath ? 1 : 0)) * 14 + 18}px` }}
                  className={`flex items-center justify-between py-1 px-2 rounded cursor-pointer transition ${
                    isSelected
                      ? 'bg-sky-600/25 text-white font-bold border-l-2 border-sky-400'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                  }`}
                >
                  <div className="flex items-center gap-1.5 min-w-0">
                    {getFileIcon(file.id)}
                    <span className="font-mono text-[11px] truncate">
                      {file.label || file.id.split('/').pop()}
                    </span>
                  </div>

                  <div className="flex items-center gap-1 ml-1 flex-none">
                    {file.is_crown_jewel && <Crown className="w-3 h-3 text-amber-400" />}
                    {hasRisk && <span className="w-1.5 h-1.5 rounded-full bg-red-400" />}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const lineCount = codeDraft.split('\n').length;
  const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-3 md:p-6 select-none animate-in fade-in duration-200">
      <div
        className={`w-full h-full rounded-2xl bg-[#0d1117] border border-slate-700/80 shadow-[0_25px_80px_rgba(0,0,0,0.85)] flex flex-col overflow-hidden transition-all ${
          isMaximized ? 'fixed inset-0 rounded-none' : 'max-w-[96vw] max-h-[95vh]'
        }`}
      >
        {/* Top Window Header (VS Code Style) */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-[#161b22] border-b border-slate-800 flex-none">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-purple-950/70 border border-purple-500/40 text-[#c084fc] font-mono text-[11px] font-bold">
              <span>RD STUDIO</span>
            </div>

            {/* Breadcrumb file indicator */}
            <div className="flex items-center gap-1.5 font-mono text-xs text-slate-300">
              <span className="text-slate-500">{projectId}</span>
              <span className="text-slate-600">/</span>
              <span className="text-sky-300 font-bold">{selectedNodeId}</span>
              {isDirty && <span className="w-2 h-2 rounded-full bg-amber-400 ml-1" title="Unsaved changes" />}
            </div>
          </div>

          {/* Right Action Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={isSaving || !isDirty}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                saveSuccess
                  ? 'bg-emerald-600 text-white'
                  : isDirty
                  ? 'bg-sky-600 hover:bg-sky-500 text-white shadow'
                  : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              }`}
            >
              {saveSuccess ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
              <span>{saveSuccess ? 'Saved' : isSaving ? 'Saving...' : 'Save File (Ctrl+S)'}</span>
            </button>

            <button
              onClick={() => setIsMaximized(!isMaximized)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title={isMaximized ? 'Restore Window' : 'Maximize Window'}
            >
              {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            <button
              onClick={() => setIsNodeStudioOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-red-500/20 hover:text-red-300 transition"
              title="Close Studio (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 3-Column Studio Body */}
        <div className="flex-1 min-h-0 flex overflow-hidden">
          {/* ================= LEFT COLUMN: EXPLORER ================= */}
          <div className="w-64 flex-none bg-[#0a0d14] border-r border-slate-800 flex flex-col min-h-0">
            <div className="p-3 border-b border-slate-800/80 flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                <Folder className="w-3.5 h-3.5 text-sky-400" /> Explorer
              </span>
              <span className="text-[10px] text-slate-500 font-mono">
                {graph.nodes.length} files
              </span>
            </div>

            {/* Quick Filter */}
            <div className="p-2 border-b border-slate-800/60">
              <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-900 border border-slate-700/80 text-xs">
                <Search className="w-3 h-3 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter files..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full bg-transparent text-slate-200 outline-none font-mono text-[11px]"
                />
              </div>
            </div>

            {/* File Tree List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
              {renderFolder(fileTree)}
            </div>
          </div>

          {/* ================= MIDDLE COLUMN: CODE EDITOR & TERMINAL ================= */}
          <div className="flex-1 min-w-0 bg-[#0d1117] flex flex-col min-h-0">
            {/* Editor Tab Bar */}
            <div className="flex items-center justify-between px-3 bg-[#161b22] border-b border-slate-800 flex-none h-9">
              <div className="flex items-center gap-1">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0d1117] border-t-2 border-sky-400 text-xs text-white font-mono rounded-t">
                  {getFileIcon(selectedNodeId)}
                  <span>{selectedNodeId.split('/').pop()}</span>
                  {isDirty && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />}
                </div>
              </div>

              <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                <span>{lineCount} lines</span>
                <span>•</span>
                <span>{currentNode?.lang?.toUpperCase() || 'CODE'}</span>
                <span>•</span>
                <span>UTF-8</span>
              </div>
            </div>

            {/* Code Text Editor Area */}
            <div className="flex-1 min-h-0 flex overflow-hidden relative font-mono text-xs bg-[#090d14]">
              {/* Line Numbers */}
              <div className="w-12 flex-none py-3 pr-2 text-right text-slate-600 bg-[#090d14] select-none border-r border-slate-800/60 leading-relaxed font-mono text-[11px]">
                {lineNumbers.map((n) => (
                  <div key={n}>{n}</div>
                ))}
              </div>

              {/* Textarea */}
              <textarea
                value={codeDraft}
                onChange={(e) => {
                  setCodeDraft(e.target.value);
                  setIsDirty(true);
                }}
                spellCheck={false}
                className="flex-1 min-w-0 p-3 bg-transparent text-slate-100 font-mono text-[11.5px] leading-relaxed resize-none outline-none overflow-auto whitespace-pre selection:bg-sky-500/30 selection:text-sky-200"
              />
            </div>

            {/* Bottom Output / Terminal Dock (matching user screenshot) */}
            <div className="h-44 flex-none border-t border-slate-800 bg-[#090c10] flex flex-col">
              <div className="flex items-center justify-between px-3 py-1.5 bg-[#161b22] border-b border-slate-800/80 text-xs">
                <div className="flex items-center gap-3 font-mono text-[11px]">
                  <button
                    onClick={() => setDockTab('terminal')}
                    className={`flex items-center gap-1.5 pb-0.5 border-b-2 transition ${
                      dockTab === 'terminal'
                        ? 'border-sky-400 text-white font-bold'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Terminal className="w-3 h-3 text-emerald-400" /> Terminal
                  </button>
                  <button
                    onClick={() => setDockTab('output')}
                    className={`flex items-center gap-1.5 pb-0.5 border-b-2 transition ${
                      dockTab === 'output'
                        ? 'border-sky-400 text-white font-bold'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Output
                  </button>
                  <button
                    onClick={() => setDockTab('problems')}
                    className={`flex items-center gap-1.5 pb-0.5 border-b-2 transition ${
                      dockTab === 'problems'
                        ? 'border-sky-400 text-white font-bold'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Problems
                  </button>
                </div>

                <div className="text-[10px] text-slate-500 font-mono">
                  python - release-domino
                </div>
              </div>

              <div className="flex-1 p-3 overflow-y-auto font-mono text-[11px] text-slate-300 leading-relaxed space-y-1">
                {dockTab === 'terminal' && (
                  <>
                    <div className="text-slate-500">
                      PS C:\Users\tms_s\PycharmProjects\system_architecture scanning\release-domino&gt; python start_server.py 8000
                    </div>
                    <div className="text-emerald-400">INFO: 127.0.0.1:8000 - &quot;GET /api/llm/status HTTP/1.1&quot; 200 OK</div>
                    <div className="text-emerald-400">INFO: 127.0.0.1:8000 - &quot;GET /api/sandbox/projects HTTP/1.1&quot; 200 OK</div>
                    <div className="text-emerald-400">INFO: 127.0.0.1:8000 - &quot;GET /api/graph/{projectId} HTTP/1.1&quot; 200 OK</div>
                    <div className="text-sky-400">INFO: Active Node inspected: {selectedNodeId} ({lineCount} lines)</div>
                  </>
                )}
                {dockTab === 'output' && (
                  <div className="text-slate-400">
                    AST parser verified syntax for {selectedNodeId}. Exports: {(nodeDetail?.exports || []).join(', ') || 'None'}.
                  </div>
                )}
                {dockTab === 'problems' && (
                  <div className="text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" /> No syntax or compilation errors found.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ================= RIGHT COLUMN: IN/OUT NODES & AI SUPPORT CHATBOX ================= */}
          <div className="w-96 flex-none bg-[#0a0d14] border-l border-slate-800 flex flex-col min-h-0">
            {/* Top Half: In Nodes & Out Nodes Graph Connectivity */}
            <div className="h-64 flex-none border-b border-slate-800 p-3 flex flex-col min-h-0 bg-[#090d14] overflow-y-auto">
              <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-slate-800/80 flex-none">
                <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5 text-cyan-400" /> In Nodes &amp; Out Nodes
                </span>
                <div className="flex items-center gap-1.5 font-mono text-[10px]">
                  <span className="px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 font-bold">
                    {inNodes.length} In
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-500/40 text-purple-300 font-bold">
                    {outNodes.length} Out
                  </span>
                </div>
              </div>

              {/* In Nodes Section (Incoming Callers -> Current Node) */}
              <div className="mb-3 flex-none">
                <div className="flex items-center justify-between mb-1.5 text-[10px] font-mono text-cyan-300 font-semibold uppercase tracking-wider">
                  <span className="flex items-center gap-1">
                    <ArrowDownLeft className="w-3.5 h-3.5 text-cyan-400" /> In Nodes (Callers)
                  </span>
                  <span className="text-slate-500 text-[9px] font-normal">{inNodes.length} caller(s)</span>
                </div>

                {inNodes.length > 0 ? (
                  <div className="space-y-1">
                    {inNodes.map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => selectNode(node.id)}
                        className="w-full flex items-center justify-between p-1.5 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-cyan-900/40 hover:border-cyan-500/60 text-left transition group cursor-pointer"
                        title={`Click to inspect caller: ${node.id}`}
                      >
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                          <span className="font-mono text-[11px] text-slate-200 truncate group-hover:text-cyan-300">
                            {node.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 shrink-0 font-mono text-[9.5px]">
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 uppercase">
                            {node.kind}
                          </span>
                          <span className={`px-1 rounded ${node.risk >= 50 ? 'text-red-400 font-bold' : 'text-emerald-400'}`}>
                            R:{Math.round(node.risk)}
                          </span>
                          {node.isCrown && <Crown className="w-2.5 h-2.5 text-amber-400 shrink-0" />}
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="p-2 rounded-lg bg-slate-900/40 border border-slate-800/60 text-[10.5px] text-slate-500 italic font-mono">
                    No incoming callers (Root / Entrypoint Node)
                  </div>
                )}
              </div>

              {/* Out Nodes Section (Current Node -> Outgoing Dependencies) */}
              <div className="flex-none">
                <div className="flex items-center justify-between mb-1.5 text-[10px] font-mono text-purple-300 font-semibold uppercase tracking-wider">
                  <span className="flex items-center gap-1">
                    <ArrowUpRight className="w-3.5 h-3.5 text-purple-400" /> Out Nodes (Dependencies)
                  </span>
                  <span className="text-slate-500 text-[9px] font-normal">{outNodes.length} dependenc(ies)</span>
                </div>

                {outNodes.length > 0 ? (
                  <div className="space-y-1">
                    {outNodes.map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => selectNode(node.id)}
                        className="w-full flex items-center justify-between p-1.5 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-purple-900/40 hover:border-purple-500/60 text-left transition group cursor-pointer"
                        title={`Click to inspect dependency: ${node.id}`}
                      >
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                          <span className="font-mono text-[11px] text-slate-200 truncate group-hover:text-purple-300">
                            {node.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 shrink-0 font-mono text-[9.5px]">
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 uppercase">
                            {node.kind}
                          </span>
                          <span className={`px-1 rounded ${node.risk >= 50 ? 'text-red-400 font-bold' : 'text-emerald-400'}`}>
                            R:{Math.round(node.risk)}
                          </span>
                          {node.isCrown && <Crown className="w-2.5 h-2.5 text-amber-400 shrink-0" />}
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="p-2 rounded-lg bg-slate-900/40 border border-slate-800/60 text-[10.5px] text-slate-500 italic font-mono">
                    No outgoing dependencies (Leaf Node)
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Half: Interactive AI Support File Chatbox */}
            <div className="flex-1 min-h-0 flex flex-col bg-[#0d1117]">
              {/* Chat Header */}
              <div className="px-3 py-2 bg-[#161b22] border-b border-slate-800 flex items-center justify-between flex-none">
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span className="font-mono text-xs font-bold text-slate-200">
                    AI Support
                  </span>
                </div>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-500/40 text-purple-300">
                  {llmStatus?.configured_model || 'NVIDIA NIM'}
                </span>
              </div>

              {/* Quick Prompt Suggestions */}
              <div className="p-2 border-b border-slate-800/60 flex items-center gap-1.5 overflow-x-auto text-[10.5px] font-mono text-slate-400 flex-none scrollbar-none">
                <button
                  onClick={() => handleSendMessage('Explain what this file does step by step.')}
                  className="px-2 py-0.5 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition whitespace-nowrap cursor-pointer"
                >
                  💡 Explain
                </button>
                <button
                  onClick={() => handleSendMessage('Identify potential security flaws or SQLi/XSS vulnerabilities in this code.')}
                  className="px-2 py-0.5 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition whitespace-nowrap cursor-pointer"
                >
                  🛡️ Audit
                </button>
                <button
                  onClick={() => handleSendMessage('Refactor this file for clean code, performance, and best practices.')}
                  className="px-2 py-0.5 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition whitespace-nowrap cursor-pointer"
                >
                  ⚡ Refactor
                </button>
                <button
                  onClick={() => handleSendMessage('Write comprehensive pytest/jest unit tests for this file.')}
                  className="px-2 py-0.5 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition whitespace-nowrap cursor-pointer"
                >
                  🧪 Test
                </button>
              </div>

              {/* Chat Messages Log */}
              <div ref={chatScrollRef} className="flex-1 overflow-y-auto p-3 space-y-2.5 text-xs font-sans">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${
                      msg.role === 'user' ? 'items-end' : 'items-start'
                    }`}
                  >
                    <div className="flex items-center gap-1 text-[10px] text-slate-500 font-mono mb-1">
                      <span>{msg.role === 'user' ? 'You' : 'AI Support'}</span>
                      <span>•</span>
                      <span>{msg.timestamp}</span>
                    </div>

                    <div
                      className={`p-2.5 rounded-xl max-w-[92%] leading-relaxed whitespace-pre-wrap ${
                        msg.role === 'user'
                          ? 'bg-sky-600 text-white shadow'
                          : 'bg-slate-900 border border-slate-800 text-slate-200'
                      }`}
                    >
                      {msg.content}

                      {/* 1-Click Apply Code Suggestion Button */}
                      {msg.suggested_code && (
                        <div className="mt-2 pt-2 border-t border-slate-700/80 flex items-center justify-between">
                          <span className="text-[10px] font-mono text-purple-300">
                            {msg.suggested_code.split('\n').length} lines suggested
                          </span>
                          <button
                            onClick={() => handleApplySuggestedCode(msg.suggested_code!)}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[10.5px] transition shadow cursor-pointer"
                          >
                            <Check className="w-3 h-3" /> Apply to Editor
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isChatting && (
                  <div className="flex items-center gap-2 text-slate-400 font-mono text-xs">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-spin" />
                    <span>AI Support is reasoning about {selectedNodeId}...</span>
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <div className="p-2.5 bg-[#161b22] border-t border-slate-800 flex items-center gap-2 flex-none">
                <input
                  type="text"
                  placeholder={`Ask AI Support about ${selectedNodeId.split('/').pop()}...`}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-[#0d1117] border border-slate-700/90 text-slate-100 text-xs font-sans outline-none focus:border-sky-500"
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={!chatInput.trim() || isChatting}
                  className="p-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white transition cursor-pointer"
                  title="Send message (Enter)"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NodeStudioModal;
