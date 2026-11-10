import React, { useState } from 'react';
import {
  X,
  Sparkles,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Zap,
  RefreshCw,
  Server,
  Key,
  Shield,
  Layers,
  Activity,
  Terminal,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const AiInspectorModal: React.FC = () => {
  const {
    isAiInspectorOpen,
    setIsAiInspectorOpen,
    llmStatus,
    testLlmConnection,
    updateLlmConfig,
    fetchInitialWorkspace,
    projectId,
  } = useReleaseStore();

  const [testResult, setTestResult] = useState<any | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  const [customKey, setCustomKey] = useState('');
  const [selectedModel, setSelectedModel] = useState(
    llmStatus?.model_id || 'nvidia/nemotron-3.5-bolt-e4b'
  );
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  if (!isAiInspectorOpen) return null;

  const handleRunPingTest = async () => {
    setIsTesting(true);
    setTestError(null);
    setTestResult(null);
    try {
      const res = await testLlmConnection();
      if (res.status === 'success') {
        setTestResult(res);
      } else {
        setTestError(res.error || 'AI ping test failed');
      }
    } catch (err: any) {
      setTestError(err?.message || 'Failed to ping AI service');
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customKey.trim() && !selectedModel.trim()) return;
    setIsSaving(true);
    setSaveMessage(null);
    try {
      const keyToSave = customKey.trim() || (llmStatus?.nvidia_configured ? 'KEEP_EXISTING' : '');
      const ok = await updateLlmConfig(keyToSave, selectedModel);
      if (ok) {
        setSaveMessage('✓ AI Model and Configuration saved and reloaded!');
        setCustomKey('');
        await fetchInitialWorkspace(projectId);
      } else {
        setSaveMessage('Failed to update AI configuration');
      }
    } catch (err: any) {
      setSaveMessage(`Error: ${err?.message || 'Could not update configuration'}`);
    } finally {
      setIsSaving(false);
    }
  };

  const activeProvider = llmStatus?.provider_name || (llmStatus?.nvidia_configured ? 'NVIDIA NIM' : 'Local Ollama');
  const activeModel = llmStatus?.model_id || llmStatus?.configured_model || 'nvidia/nemotron-3.5-bolt-e4b';
  const endpointUrl = llmStatus?.endpoint_url || 'https://integrate.api.nvidia.com/v1';
  const maskedKey = llmStatus?.masked_key || 'Configured via .env';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700/90 shadow-2xl flex flex-col max-h-[92vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  Active AI Engine Inspector
                </h2>
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10.5px] font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
                  ONLINE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Detailed runtime inspection of the AI powering node synthesis, dependency wiring, and test healing.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsAiInspectorOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
          {/* Active Model Snapshot Card */}
          <div className="p-4 rounded-xl bg-gradient-to-br from-purple-950/40 via-slate-950 to-slate-950 border border-purple-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase tracking-wider text-purple-400 font-bold flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" />
                Active Primary Inference Provider
              </span>
              <span className="px-2 py-0.5 rounded bg-purple-900/60 border border-purple-500/40 text-purple-200 font-mono text-[11px]">
                {activeProvider}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-1">
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                  <Server className="w-3 h-3 text-sky-400" /> Active Model
                </span>
                <p className="font-mono font-bold text-slate-100 text-xs truncate" title={activeModel}>
                  {activeModel}
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                  <Activity className="w-3 h-3 text-emerald-400" /> API Base Endpoint
                </span>
                <p className="font-mono font-bold text-slate-100 text-xs truncate" title={endpointUrl}>
                  {endpointUrl}
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                  <Key className="w-3 h-3 text-amber-400" /> API Key (Masked)
                </span>
                <p className="font-mono font-bold text-slate-100 text-xs">
                  {maskedKey}
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                  <Layers className="w-3 h-3 text-purple-400" /> Fallback Providers
                </span>
                <p className="font-mono text-slate-200 text-xs truncate">
                  {llmStatus?.fallback_provider || 'DeepSeek Flash / Ollama'}
                </p>
              </div>
            </div>

            {/* Architecture Guardrails Pill */}
            <div className="flex items-center gap-2 pt-2 border-t border-purple-900/40 text-[11px] text-slate-300">
              <Shield className="w-3.5 h-3.5 text-emerald-400" />
              <span>AST Syntax Check + Automated Secret Redaction + Formatting Style Preservation</span>
            </div>
          </div>

          {/* Live Ping Test */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-amber-400" /> Live AI Inference Verification
                </h3>
                <p className="text-[11px] text-slate-400">
                  Send a live test request to verify round-trip response and measure latency.
                </p>
              </div>
              <button
                type="button"
                onClick={handleRunPingTest}
                disabled={isTesting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold transition disabled:opacity-50 cursor-pointer shadow"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
                {isTesting ? 'Pinging AI...' : 'Run Live Ping Test'}
              </button>
            </div>

            {testError && (
              <div className="p-2.5 rounded-lg bg-rose-950/60 border border-rose-500/50 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{testError}</span>
              </div>
            )}

            {testResult && (
              <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/40 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="flex items-center gap-1.5 text-emerald-300 font-bold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Round-trip Ping Successful ({testResult.latency_ms} ms)
                  </span>
                  <span className="text-slate-400">Provider: {testResult.provider}</span>
                </div>
                <div className="p-2 rounded bg-black/60 font-mono text-[10.5px] text-slate-300 overflow-x-auto">
                  <pre>{JSON.stringify(testResult.response, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Quick Model Selector & Config */}
          <form onSubmit={handleSaveConfig} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <div>
              <h3 className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
                <Terminal className="w-4 h-4 text-sky-400" /> Switch NVIDIA NIM Model or Update API Key
              </h3>
              <p className="text-[11px] text-slate-400">
                Switch models dynamically or update your API key without restarting the backend.
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-[10.5px] font-semibold text-slate-300">Select Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono text-xs focus:border-purple-500 outline-none cursor-pointer"
              >
                <option value="nvidia/nemotron-3.5-bolt-e4b">
                  nvidia/nemotron-3.5-bolt-e4b (Active — High-Precision Code Reasoning)
                </option>
                <option value="meta/llama-3.1-70b-instruct">
                  meta/llama-3.1-70b-instruct (Frontier 70B parameter model)
                </option>
                <option value="meta/llama-3.1-8b-instruct">
                  meta/llama-3.1-8b-instruct (Fast 8B parameter model)
                </option>
                <option value="qwen/qwen2.5-coder-32b-instruct">
                  qwen/qwen2.5-coder-32b-instruct (32B specialized coding model)
                </option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-[10.5px] font-semibold text-slate-300">
                New API Key (optional — leave empty to keep current key)
              </label>
              <input
                type="password"
                value={customKey}
                onChange={(e) => setCustomKey(e.target.value)}
                placeholder="nvapi-... or sk-..."
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono text-xs focus:border-purple-500 outline-none"
              />
            </div>

            {saveMessage && (
              <div
                className={`p-2 rounded text-xs ${
                  saveMessage.startsWith('✓')
                    ? 'bg-emerald-950/60 border border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/60 border border-rose-500/40 text-rose-300'
                }`}
              >
                {saveMessage}
              </div>
            )}

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold transition disabled:opacity-50 cursor-pointer text-xs"
              >
                {isSaving ? 'Saving...' : 'Apply & Reload Configuration'}
              </button>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs text-slate-400">
          <span className="font-mono text-[10.5px]">
            Disk Cache: <code className="text-slate-300">.llm_cache/</code> | Fallback Ready: Yes
          </span>
          <button
            onClick={() => setIsAiInspectorOpen(false)}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
