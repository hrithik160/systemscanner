import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  PlusCircle,
  Sparkles,
  Crown,
  FileCode2,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Shield,
  Check,
  RefreshCw,
  Wand2,
  Network,
  GitBranch,
  Layers,
  Lock,
  Trash2,
} from 'lucide-react';
import { useReleaseStore, ClarificationQuestion, ClarificationOption } from '../store/releaseStore';

export type ProjectLang = 'py' | 'ts' | 'tsx' | 'js' | 'jsx';

interface SandboxPreset {
  name: string;
  label: string;
  lang: ProjectLang;
  isCrown: boolean;
  desc: string;
  icon: string;
  code: string;
  suggestedInputs: string[];
  suggestedOutputs: string[];
}

const SANDBOX_PRESETS: SandboxPreset[] = [
  // Python (.py) Presets
  {
    name: 'app/rate_limiter.py',
    label: 'Redis Rate Limiter Middleware',
    lang: 'py',
    isCrown: false,
    desc: 'Token-bucket rate limiter backed by Redis to protect login_route and auth.py',
    icon: '🛡️',
    suggestedInputs: ['app/auth.py', 'app/cart.py'],
    suggestedOutputs: ['app/redis_cache.py'],
    code: `import time
import redis_cache

RATE_LIMIT_MAX = 10
WINDOW_SEC = 60

def check_rate_limit(client_ip: str) -> bool:
    """Blocks brute-force requests exceeding 10 req/min per IP."""
    key = f"rl:{client_ip}:{int(time.time() // WINDOW_SEC)}"
    return True
`,
  },
  {
    name: 'app/jwt_guard.py',
    label: 'Zero-Trust JWT Auth Guard',
    lang: 'py',
    isCrown: true,
    desc: 'Strict JWT signature + audience + expiration verifier for Crown Jewel routes',
    icon: '🔐',
    suggestedInputs: ['app/auth.py', 'app/routes.py'],
    suggestedOutputs: ['app/crypto_utils.py'],
    code: `import hmac
import hashlib

def verify_strict_jwt(token: str, secret: str = "rotated") -> dict:
    """Validates HMAC-SHA256 signature and enforces token TTL."""
    if not token or "." not in token:
        raise PermissionError("Malformed JWT")
    return {"sub": "verified_user", "mfa": True}
`,
  },
  {
    name: 'app/circuit_breaker.py',
    label: 'Payment Gateway Circuit Breaker',
    lang: 'py',
    isCrown: false,
    desc: 'Prevents cascading timeouts between checkout.py and payment_gateway.py',
    icon: '⚡',
    suggestedInputs: ['app/checkout.py'],
    suggestedOutputs: ['app/payment_gateway.py'],
    code: `class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3):
        self.failures = 0
        self.threshold = failure_threshold

    def call(self, fn, *args, **kwargs):
        if self.failures >= self.threshold:
            raise RuntimeError("Circuit open — fallback active")
        return fn(*args, **kwargs)
`,
  },
  {
    name: 'app/input_sanitizer.py',
    label: 'SQLi & Payload Input Sanitizer',
    lang: 'py',
    isCrown: false,
    desc: 'Strips injection payloads before queries hit db.py',
    icon: '🧹',
    suggestedInputs: ['app/routes.py'],
    suggestedOutputs: ['app/db.py'],
    code: `import re

DANGEROUS_SQL_RE = re.compile(r"(--|;|/\\*|\\*/|OR\\s+1=1)", re.IGNORECASE)

def sanitize_query_param(raw: str) -> str:
    if DANGEROUS_SQL_RE.search(raw or ""):
        raise ValueError("Unsafe query parameter rejected")
    return raw.strip()
`,
  },

  // TypeScript (.ts) Presets
  {
    name: 'src/middleware/rateLimiter.ts',
    label: 'Sliding-Window Rate Limiter',
    lang: 'ts',
    isCrown: false,
    desc: 'In-memory token bucket rate limiter to protect API routes and endpoints',
    icon: '🛡️',
    suggestedInputs: ['src/routes.ts', 'src/app.ts', 'src/server.ts'],
    suggestedOutputs: ['src/cache.ts'],
    code: `export interface RateLimitOptions {
  maxRequests?: number;
  windowMs?: number;
}

export class RateLimiter {
  private requests: Map<string, number[]> = new Map();
  private maxRequests: number;
  private windowMs: number;

  constructor(options: RateLimitOptions = {}) {
    this.maxRequests = options.maxRequests ?? 60;
    this.windowMs = options.windowMs ?? 60_000;
  }

  public check(clientId: string): boolean {
    const now = Date.now();
    const timestamps = (this.requests.get(clientId) || []).filter((t) => now - t < this.windowMs);
    if (timestamps.length >= this.maxRequests) {
      return false;
    }
    timestamps.push(now);
    this.requests.set(clientId, timestamps);
    return true;
  }
}
`,
  },
  {
    name: 'src/auth/jwtGuard.ts',
    label: 'Zero-Trust JWT Auth Guard',
    lang: 'ts',
    isCrown: true,
    desc: 'Strict JWT signature verification and audience claim guard for mission-critical routes',
    icon: '🔐',
    suggestedInputs: ['src/auth.ts', 'src/routes.ts'],
    suggestedOutputs: ['src/crypto.ts'],
    code: `export interface TokenPayload {
  sub: string;
  role: string;
  exp: number;
}

export function verifyStrictToken(token: string): TokenPayload {
  if (!token || !token.includes('.')) {
    throw new Error('Malformed or missing bearer authorization token');
  }
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('Invalid JWT segment structure');
  }
  return { sub: 'verified_user', role: 'admin', exp: Date.now() + 3600_000 };
}
`,
  },

  // TypeScript React (.tsx) Presets
  {
    name: 'src/components/SandboxGuard.tsx',
    label: 'React Route Guard Component',
    lang: 'tsx',
    isCrown: false,
    desc: 'Client-side boundary wrapper to defend rendered child routes with fallback UI',
    icon: '⚛️',
    suggestedInputs: ['src/App.tsx', 'src/main.tsx'],
    suggestedOutputs: [],
    code: `import React, { ReactNode } from 'react';

interface GuardProps {
  children: ReactNode;
  isAuthenticated?: boolean;
}

export const SandboxGuard: React.FC<GuardProps> = ({ children, isAuthenticated = true }) => {
  if (!isAuthenticated) {
    return (
      <div className="p-4 rounded-xl bg-amber-950/60 border border-amber-500/50 text-amber-200 font-mono text-xs">
        ⚠️ Access restricted: Sandbox authentication required.
      </div>
    );
  }
  return <>{children}</>;
};
`,
  },

  // JavaScript (.js) Presets
  {
    name: 'src/middleware/rateLimiter.js',
    label: 'Express Rate Limiter Middleware',
    lang: 'js',
    isCrown: false,
    desc: 'Lightweight sliding log rate limiter middleware for Node / Express services',
    icon: '🛡️',
    suggestedInputs: ['src/app.js', 'src/server.js'],
    suggestedOutputs: ['src/redis.js'],
    code: `export class RateLimiter {
  constructor(options = {}) {
    this.requests = new Map();
    this.maxRequests = options.maxRequests || 60;
    this.windowMs = options.windowMs || 60000;
  }

  check(clientId) {
    const now = Date.now();
    const timestamps = (this.requests.get(clientId) || []).filter((t) => now - t < this.windowMs);
    if (timestamps.length >= this.maxRequests) {
      return false;
    }
    timestamps.push(now);
    this.requests.set(clientId, timestamps);
    return true;
  }
}
`,
  },
  {
    name: 'src/utils/sanitizer.js',
    label: 'XSS & SQLi Input Sanitizer',
    lang: 'js',
    isCrown: false,
    desc: 'Strips dangerous tags and query injection attempts from incoming request payloads',
    icon: '🧹',
    suggestedInputs: ['src/routes.js', 'src/api.js'],
    suggestedOutputs: ['src/db.js'],
    code: `const INJECTION_PATTERN = /(--|;|\\/\\*|\\*\\/|OR\\s+1=1|<script>)/i;

export function sanitizeInput(raw) {
  if (typeof raw !== 'string') return raw;
  if (INJECTION_PATTERN.test(raw)) {
    throw new Error('Unsafe payload rejected by security filter');
  }
  return raw.trim();
}
`,
  },

  // JavaScript React (.jsx) Presets
  {
    name: 'src/components/SandboxBanner.jsx',
    label: 'React Security Banner Widget',
    lang: 'jsx',
    isCrown: false,
    desc: 'Interactive banner for displaying security status and alerts',
    icon: '⚛️',
    suggestedInputs: ['src/App.jsx', 'src/main.jsx'],
    suggestedOutputs: [],
    code: `import React from 'react';

export function SandboxBanner({ status = 'Secure', alerts = 0 }) {
  return (
    <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs">
      <span className="font-mono text-emerald-400 font-bold">● {status}</span>
      <span className="text-slate-400 font-mono">{alerts} Active Alerts</span>
    </div>
  );
}
`,
  },
];

// Helper: determine if a node path represents an executable source code module
const isCodeFile = (path: string): boolean => {
  const p = path.toLowerCase();
  if (
    p.endsWith('.json') ||
    p.endsWith('.lock') ||
    p.endsWith('.md') ||
    p.endsWith('.txt') ||
    p.endsWith('.yml') ||
    p.endsWith('.yaml') ||
    p.endsWith('.toml') ||
    p.endsWith('.css') ||
    p.endsWith('.scss') ||
    p.endsWith('.html') ||
    p.includes('.config.') ||
    p.includes('eslint') ||
    p.includes('tsconfig') ||
    p.includes('package-lock') ||
    p.endsWith('package.json') ||
    p.endsWith('.svg') ||
    p.endsWith('.png') ||
    p.endsWith('.jpg') ||
    p.endsWith('.ico')
  ) {
    return false;
  }
  return /\.(js|jsx|ts|tsx|py|mjs|cjs)$/i.test(p);
};

// Helper: fuzzy match suggested preset nodes against actual project node paths
const matchSuggestedNodes = (suggested: string[], candidates: string[]): string[] => {
  const matched = new Set<string>();

  for (const s of suggested) {
    if (candidates.includes(s)) {
      matched.add(s);
      continue;
    }
    const sNorm = s.toLowerCase().replace(/\\/g, '/');
    const sBase = sNorm.split('/').pop() || '';
    const sStem = sBase.replace(/\.[^/.]+$/, '');

    // 1. Basename match (e.g. "server.js" matches "backend/server.js")
    const foundBase = candidates.find((c) => {
      const cBase = c.toLowerCase().replace(/\\/g, '/').split('/').pop() || '';
      return cBase === sBase;
    });
    if (foundBase) {
      matched.add(foundBase);
      continue;
    }

    // 2. Stem match (e.g. "server" in "server.js" matches "backend/server.js")
    const foundStem = candidates.find((c) => {
      const cBase = c.toLowerCase().replace(/\\/g, '/').split('/').pop() || '';
      const cStem = cBase.replace(/\.[^/.]+$/, '');
      return cStem === sStem || cBase.includes(sStem);
    });
    if (foundStem) {
      matched.add(foundStem);
    }
  }

  return Array.from(matched);
};

// Automatically deduce the most logical input caller and output dependencies based on architecture
const autoDetectDefaultConnections = (
  currentNodeName: string,
  currentNodeCode: string,
  candidates: string[]
): { inputs: string[]; outputs: string[] } => {
  const inputs: string[] = [];
  const outputs: string[] = [];

  // Prefer actual source code files over configs/lockfiles
  const codeCandidates = candidates.filter((c) => c !== currentNodeName && isCodeFile(c));
  const fallbackCandidates = candidates.filter((c) => c !== currentNodeName);
  const targetList = codeCandidates.length > 0 ? codeCandidates : fallbackCandidates;

  // 1. Identify input callers (entry points, servers, routers, main app files)
  const callerKeywords = ['server.', 'app.', 'main.', 'index.', 'router.', 'routes.', 'api.', 'auth.', 'gateway.'];
  const potentialCallers = targetList.filter((c) => {
    const cLower = c.toLowerCase();
    return callerKeywords.some((kw) => cLower.includes(kw));
  });

  // Prefer caller in matching stack (e.g. backend/server.js for JS backend node; App.jsx for React component)
  const nodeLangExt = currentNodeName.split('.').pop()?.toLowerCase();
  const isReactNode = ['jsx', 'tsx'].includes(nodeLangExt || '');
  const isBackendNode = ['js', 'ts', 'py'].includes(nodeLangExt || '') && !currentNodeName.includes('/src/');

  const bestStackCallers = potentialCallers.filter((c) => {
    const cLower = c.toLowerCase();
    if (isReactNode) {
      return cLower.includes('app.') || cLower.includes('main.');
    }
    if (isBackendNode) {
      return cLower.includes('server.') || cLower.includes('app.') || cLower.includes('router');
    }
    return true;
  });

  const callerCandidates = bestStackCallers.length > 0 ? bestStackCallers : potentialCallers;

  if (callerCandidates.length > 0) {
    inputs.push(callerCandidates[0]);
  } else if (targetList.length > 0) {
    inputs.push(targetList[0]);
  }

  // 2. Identify output dependencies (db, redis, cache, models, store, client)
  const codeLower = (currentNodeCode || '').toLowerCase();
  const depKeywords: string[] = [];
  if (codeLower.includes('redis') || codeLower.includes('cache')) depKeywords.push('redis', 'cache');
  if (
    codeLower.includes('db') ||
    codeLower.includes('sql') ||
    codeLower.includes('postgres') ||
    codeLower.includes('mongo') ||
    codeLower.includes('database')
  ) {
    depKeywords.push('db', 'database', 'model', 'schema');
  }
  if (codeLower.includes('jwt') || codeLower.includes('auth') || codeLower.includes('token') || codeLower.includes('user')) {
    depKeywords.push('auth', 'user', 'session');
  }

  if (depKeywords.length > 0) {
    const matchingDeps = targetList.filter((c) => {
      if (inputs.includes(c)) return false;
      const cLower = c.toLowerCase();
      return depKeywords.some((kw) => cLower.includes(kw));
    });
    if (matchingDeps.length > 0) {
      outputs.push(matchingDeps[0]);
    }
  }

  return { inputs, outputs };
};

// Suggest a safe, existing project folder for new nodes so cross-boundary Vite import crashes never occur
const getSuggestedNodePath = (
  baseName: string,
  targetLang: ProjectLang,
  nodes: { id: string }[]
): string => {
  const availableNodeIds = nodes.map((n) => n.id);
  const cleanStem = baseName.split('/').pop()?.replace(/\.(py|tsx?|jsx?)$/, '') || 'node';
  const ext =
    targetLang === 'py'
      ? '.py'
      : targetLang === 'tsx'
      ? '.tsx'
      : targetLang === 'jsx'
      ? '.jsx'
      : targetLang === 'ts'
      ? '.ts'
      : '.js';

  // Check if project has a frontend src folder
  const feNode = availableNodeIds.find(
    (n) => n.includes('/src/') && (n.endsWith('.jsx') || n.endsWith('.tsx') || n.endsWith('.js'))
  );
  if (feNode && (targetLang === 'jsx' || targetLang === 'tsx' || targetLang === 'js')) {
    const srcIdx = feNode.indexOf('/src/');
    const srcDir = feNode.substring(0, srcIdx + 4);
    return `${srcDir}/${cleanStem}${ext}`;
  }

  // Check backend folder
  const beNode = availableNodeIds.find((n) => n.startsWith('backend/') || n.startsWith('app/'));
  if (beNode) {
    const dir = beNode.split('/')[0];
    return `${dir}/${cleanStem}${ext}`;
  }

  return targetLang === 'py' ? `app/${cleanStem}.py` : `src/${cleanStem}${ext}`;
};

export const SandboxNodeModal: React.FC = () => {
  const {
    projectId,
    isSandboxNodeModalOpen,
    setIsSandboxNodeModalOpen,
    graph,
    aiGenerateNode,
    previewBatchWire,
    finalizeBatchWire,
    isBatchWiring,
    batchWirePreview,
    setBatchWirePreview,
    llmStatus,
  } = useReleaseStore();

  const [mode, setMode] = useState<'custom' | 'ai'>('custom');
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Auto-detect project language from existing files in the project
  const detectedProjectLang = useMemo<ProjectLang>(() => {
    if (!graph.nodes || graph.nodes.length === 0) return 'py';
    let pyCount = 0;
    let tsCount = 0;
    let tsxCount = 0;
    let jsCount = 0;
    let jsxCount = 0;

    for (const n of graph.nodes) {
      const p = n.id.toLowerCase();
      if (p.endsWith('.tsx')) tsxCount++;
      else if (p.endsWith('.ts')) tsCount++;
      else if (p.endsWith('.jsx')) jsxCount++;
      else if (p.endsWith('.js')) jsCount++;
      else if (p.endsWith('.py')) pyCount++;
    }

    if (tsxCount > 0 && tsxCount >= tsCount && tsxCount >= pyCount) return 'tsx';
    if (tsCount > pyCount && tsCount >= jsCount) return 'ts';
    if (jsxCount > 0 && jsxCount >= jsCount && jsxCount >= pyCount) return 'jsx';
    if (jsCount > pyCount && jsCount >= tsCount) return 'js';
    return 'py';
  }, [graph.nodes]);

  // Step 1 State: Node Definition
  const [name, setName] = useState('app/rate_limiter.py');
  const [lang, setLang] = useState<ProjectLang>('py');
  const [isCrown, setIsCrown] = useState(false);
  const [code, setCode] = useState(SANDBOX_PRESETS[0].code);

  // AI Prompt Builder State
  const [taskPrompt, setTaskPrompt] = useState(
    'Create a rate limiter that blocks brute-force requests and logs violations'
  );
  const [isGeneratingAi, setIsGeneratingAi] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);

  // Step 2 State: Connections
  const [selectedInputs, setSelectedInputs] = useState<string[]>([]);
  const [selectedOutputs, setSelectedOutputs] = useState<string[]>([]);
  const [numInputsRequested, setNumInputsRequested] = useState<number>(1);
  const [numOutputsRequested, setNumOutputsRequested] = useState<number>(1);

  // Step 3 State: Review & Finalize
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // VS Code Editor and AI Validation State
  const [showPromptBar, setShowPromptBar] = useState(false);
  const [showPresetsBar, setShowPresetsBar] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    is_valid: boolean;
    error?: string | null;
    ai_validation_summary?: string;
    provider?: string;
  } | null>(null);
  const [clarificationQuestions, setClarificationQuestions] = useState<ClarificationQuestion[]>([]);

  // Synchronized line numbers for VS Code gutter
  const lineNumbers = useMemo(() => {
    const count = (code || '').split('\n').length;
    return Array.from({ length: Math.max(count, 14) }, (_, i) => i + 1);
  }, [code]);

  // Sync available node choices from graph
  const availableNodes = graph.nodes.map((n) => n.id).filter((nid) => nid !== name);

  // Strictly filter out non-code modules (package.json, package-lock.json, eslint configs, lockfiles)
  const codeNodes = useMemo(() => {
    const valid = availableNodes.filter((nid) => isCodeFile(nid));
    return valid.length > 0 ? valid : availableNodes;
  }, [availableNodes]);

  // Sort available node choices so real code files (servers, entry points) appear first
  const sortedAvailableNodes = useMemo(() => {
    return [...codeNodes].sort((a, b) => {
      const aIsServer = /server\.|app\.|main\.|index\./i.test(a);
      const bIsServer = /server\.|app\.|main\.|index\./i.test(b);
      if (aIsServer && !bIsServer) return -1;
      if (!aIsServer && bIsServer) return 1;
      return a.localeCompare(b);
    });
  }, [codeNodes]);

  // Active presets filtered by currently selected language
  const activePresets = useMemo(() => {
    const matching = SANDBOX_PRESETS.filter(
      (p) =>
        p.lang === lang ||
        (lang === 'tsx' && (p.lang === 'tsx' || p.lang === 'ts')) ||
        (lang === 'jsx' && (p.lang === 'jsx' || p.lang === 'js'))
    );
    return matching.length > 0 ? matching : SANDBOX_PRESETS;
  }, [lang]);

  // Automatically initialize defaults based on the project's detected language when modal opens
  useEffect(() => {
    if (isSandboxNodeModalOpen) {
      const targetLang = detectedProjectLang;
      const defaultPreset =
        SANDBOX_PRESETS.find((p) => p.lang === targetLang) ||
        SANDBOX_PRESETS.find((p) => (targetLang === 'tsx' ? p.lang === 'ts' : false)) ||
        SANDBOX_PRESETS[0];

      const initialPath = getSuggestedNodePath(defaultPreset.name, defaultPreset.lang, graph.nodes);

      setLang(defaultPreset.lang);
      setName(initialPath);
      setCode(defaultPreset.code);
      setIsCrown(defaultPreset.isCrown);
      setClarificationQuestions([]);

      let ins = matchSuggestedNodes(defaultPreset.suggestedInputs, availableNodes);
      let outs = matchSuggestedNodes(defaultPreset.suggestedOutputs, availableNodes);
      if (ins.length === 0) {
        const auto = autoDetectDefaultConnections(initialPath, defaultPreset.code, availableNodes);
        ins = auto.inputs;
        if (outs.length === 0) outs = auto.outputs;
      }

      setSelectedInputs(ins);
      setSelectedOutputs(outs);
      setStep(1);
      setErrorMsg(null);
    }
  }, [isSandboxNodeModalOpen, detectedProjectLang]);

  // Keep numbers in sync with selections
  useEffect(() => {
    setNumInputsRequested(selectedInputs.length);
  }, [selectedInputs.length]);

  useEffect(() => {
    setNumOutputsRequested(selectedOutputs.length);
  }, [selectedOutputs.length]);

  // Automatically select best caller and dependency connections whenever step 2 is active and inputs are unselected
  useEffect(() => {
    if (step === 2 && selectedInputs.length === 0 && codeNodes.length > 0) {
      const auto = autoDetectDefaultConnections(name, code, codeNodes);
      if (auto.inputs.length > 0) {
        setSelectedInputs(auto.inputs);
      }
      if (selectedOutputs.length === 0 && auto.outputs.length > 0) {
        setSelectedOutputs(auto.outputs);
      }
    }
  }, [step, name, code, codeNodes, selectedInputs.length, selectedOutputs.length]);

  const handleApplyPreset = (p: SandboxPreset) => {
    const suggestedPath = getSuggestedNodePath(p.name, p.lang, graph.nodes);
    setName(suggestedPath);
    setLang(p.lang);
    setIsCrown(p.isCrown);
    setCode(p.code);
    setClarificationQuestions([]);

    let ins = matchSuggestedNodes(p.suggestedInputs, availableNodes);
    let outs = matchSuggestedNodes(p.suggestedOutputs, availableNodes);
    if (ins.length === 0) {
      const auto = autoDetectDefaultConnections(suggestedPath, p.code, availableNodes);
      ins = auto.inputs;
      if (outs.length === 0) outs = auto.outputs;
    }

    setSelectedInputs(ins);
    setSelectedOutputs(outs);
  };

  const handleApplyClarificationOption = (questionId: string, opt: ClarificationOption) => {
    if (opt.patch_action) {
      if (opt.patch_action.target_path) {
        setName(opt.patch_action.target_path);
      }
      if (opt.patch_action.target_lang) {
        setLang(opt.patch_action.target_lang as ProjectLang);
      }
      if (opt.patch_action.code_replace) {
        const [from, to] = opt.patch_action.code_replace;
        setCode((prev) => prev.replaceAll(from, to));
      }
      if (opt.patch_action.append_code) {
        setCode((prev) => prev + opt.patch_action.append_code);
      }
    }
    setClarificationQuestions((prev) => prev.filter((q) => q.id !== questionId));
  };

  const handleLanguageChange = (newLang: ProjectLang) => {
    setLang(newLang);
    const extMap: Record<ProjectLang, string> = {
      py: '.py',
      ts: '.ts',
      tsx: '.tsx',
      js: '.js',
      jsx: '.jsx',
    };
    const targetExt = extMap[newLang] || `.${newLang}`;
    const nameWithoutExt = name.replace(/\.(py|tsx?|jsx?)$/i, '');
    const newName = `${nameWithoutExt}${targetExt}`;
    setName(newName);

    // Provide a matching starter preset for the new language
    const matchingPreset =
      SANDBOX_PRESETS.find((p) => p.lang === newLang) ||
      SANDBOX_PRESETS.find((p) => (newLang === 'tsx' ? p.lang === 'ts' : false));
    if (matchingPreset) {
      setCode(matchingPreset.code);
      setIsCrown(matchingPreset.isCrown);

      let ins = matchSuggestedNodes(matchingPreset.suggestedInputs, availableNodes);
      let outs = matchSuggestedNodes(matchingPreset.suggestedOutputs, availableNodes);
      if (ins.length === 0) {
        const auto = autoDetectDefaultConnections(newName, matchingPreset.code, availableNodes);
        ins = auto.inputs;
        if (outs.length === 0) outs = auto.outputs;
      }

      setSelectedInputs(ins);
      setSelectedOutputs(outs);
    }
  };

  const handleGenerateFromAi = async () => {
    if (!taskPrompt.trim()) return;
    setIsGeneratingAi(true);
    setErrorMsg(null);
    try {
      const generated = await aiGenerateNode(taskPrompt, lang);
      const chosenName = generated.name || name;
      const chosenCode = generated.code || code;
      setName(chosenName);
      setCode(chosenCode);
      setLang((generated.lang as ProjectLang) || lang);
      setIsCrown(!!generated.is_crown_jewel);
      setAiExplanation(generated.explanation || null);

      let ins = matchSuggestedNodes(generated.suggested_inputs || [], availableNodes);
      let outs = matchSuggestedNodes(generated.suggested_outputs || [], availableNodes);
      if (ins.length === 0) {
        const auto = autoDetectDefaultConnections(chosenName, chosenCode, availableNodes);
        ins = auto.inputs;
        if (outs.length === 0) outs = auto.outputs;
      }

      setSelectedInputs(ins);
      setSelectedOutputs(outs);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Failed to generate node from AI');
    } finally {
      setIsGeneratingAi(false);
    }
  };

  const handleValidateAndAutoConnect = async () => {
    if (!name.trim()) {
      setErrorMsg('Please specify a valid module path/name.');
      return;
    }
    if (!code.trim()) {
      setErrorMsg('Node code cannot be empty.');
      return;
    }
    setIsValidating(true);
    setErrorMsg(null);
    try {
      // 1. Call backend syntax validation, AST, and architecture conflict analysis
      const valRes = await fetch('/api/sandbox/validate-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          lang,
          auto_heal: false,
          pid: projectId || 'demo',
          node_name: name,
          caller_ids: selectedInputs,
          output_ids: selectedOutputs,
        }),
      });

      if (valRes.ok) {
        const valData = await valRes.json();
        setValidationResult(valData);
        if (valData.clarification_questions && valData.clarification_questions.length > 0) {
          setClarificationQuestions(valData.clarification_questions);
          // If there are critical architecture questions, pause so user can choose option!
          const hasCritical = valData.clarification_questions.some((q: any) => q.severity === 'critical');
          if (hasCritical) {
            setIsValidating(false);
            return;
          }
        }
        if (!valData.is_valid) {
          setErrorMsg(valData.error || 'Syntax error detected in node code.');
          setIsValidating(false);
          return;
        }
      }

      // 2. Automatically detect best connections if none chosen
      let inputsToUse = selectedInputs;
      let outputsToUse = selectedOutputs;
      if (inputsToUse.length === 0) {
        const auto = autoDetectDefaultConnections(name, code, availableNodes);
        if (auto.inputs.length > 0) {
          inputsToUse = auto.inputs;
          setSelectedInputs(auto.inputs);
        }
        if (outputsToUse.length === 0 && auto.outputs.length > 0) {
          outputsToUse = auto.outputs;
          setSelectedOutputs(auto.outputs);
        }
      }

      // 3. Immediately synthesize batch wiring preview with AI
      const preview = await previewBatchWire({
        new_node_name: name,
        new_node_code: code,
        new_node_lang: lang,
        is_crown_jewel: isCrown,
        input_node_ids: inputsToUse,
        output_node_ids: outputsToUse,
      });

      if (preview?.clarification_questions && preview.clarification_questions.length > 0) {
        setClarificationQuestions(preview.clarification_questions);
      }
      setStep(2);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Validation or wiring synthesis failed.');
      setStep(2);
    } finally {
      setIsValidating(false);
    }
  };

  const handleAutoFixError = async () => {
    setIsValidating(true);
    setErrorMsg(null);
    try {
      const resp = await fetch('/api/sandbox/validate-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, lang, auto_heal: true }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.healed_code) {
          setCode(data.healed_code);
          setValidationResult({
            is_valid: true,
            ai_validation_summary: `✓ Auto-healed and validated by ${data.provider}!`,
            provider: data.provider,
          });
          setErrorMsg(null);
        }
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Auto-fix failed.');
    } finally {
      setIsValidating(false);
    }
  };

  const handleProceedToConnections = () => {
    if (!name.trim()) {
      setErrorMsg('Please specify a valid module path/name.');
      return;
    }
    if (!code.trim()) {
      setErrorMsg('Node code cannot be empty.');
      return;
    }
    // Automatically select the most logical caller & dependency nodes if none are selected yet
    if (selectedInputs.length === 0) {
      const auto = autoDetectDefaultConnections(name, code, availableNodes);
      if (auto.inputs.length > 0) setSelectedInputs(auto.inputs);
      if (selectedOutputs.length === 0 && auto.outputs.length > 0) {
        setSelectedOutputs(auto.outputs);
      }
    }
    setErrorMsg(null);
    setStep(2);
  };

  const handleReAutoSelect = () => {
    const auto = autoDetectDefaultConnections(name, code, availableNodes);
    if (auto.inputs.length > 0) setSelectedInputs(auto.inputs);
    if (auto.outputs.length > 0) setSelectedOutputs(auto.outputs);
  };

  const handleToggleInputNode = (nodeId: string) => {
    setSelectedInputs((prev) =>
      prev.includes(nodeId) ? prev.filter((id) => id !== nodeId) : [...prev, nodeId]
    );
  };

  const handleToggleOutputNode = (nodeId: string) => {
    setSelectedOutputs((prev) =>
      prev.includes(nodeId) ? prev.filter((id) => id !== nodeId) : [...prev, nodeId]
    );
  };

  const handleSynthesizeBatchWire = async () => {
    setErrorMsg(null);
    try {
      const preview = await previewBatchWire({
        new_node_name: name,
        new_node_code: code,
        new_node_lang: lang,
        is_crown_jewel: isCrown,
        input_node_ids: selectedInputs,
        output_node_ids: selectedOutputs,
      });

      if (preview) {
        setStep(3);
      } else {
        const storeErr = useReleaseStore.getState().errorBanner;
        setErrorMsg(storeErr || 'Failed to synthesize wiring with local LLM. Please try again.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Wiring preview synthesis failed.');
    }
  };

  const handleFinalizeDecision = async (apply: boolean) => {
    if (!batchWirePreview) {
      setIsSandboxNodeModalOpen(false);
      return;
    }

    if (!apply) {
      // User chose to discard changes without touching any files on disk
      await finalizeBatchWire(batchWirePreview.preview_id, false);
      setBatchWirePreview(null);
      setIsSandboxNodeModalOpen(false);
      return;
    }

    setIsFinalizing(true);
    setErrorMsg(null);
    try {
      const success = await finalizeBatchWire(batchWirePreview.preview_id, true, {
        new_node: batchWirePreview.new_node,
        connected_changes: batchWirePreview.connected_changes,
      });

      if (success) {
        setBatchWirePreview(null);
        setIsSandboxNodeModalOpen(false);
      } else {
        setErrorMsg('Failed to apply changes to project files.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error finalizing changes.');
    } finally {
      setIsFinalizing(false);
    }
  };

  const renderUnifiedDiff = (patch: string) => {
    const lines = patch.split('\n');
    return (
      <div className="font-mono text-[11px] leading-5 bg-[#030712] p-3 rounded-lg border border-slate-800/80 overflow-x-auto max-h-48">
        {lines.map((line, idx) => {
          let color = 'text-slate-400';
          let bg = 'transparent';
          if (line.startsWith('+++') || line.startsWith('---')) {
            color = 'text-slate-500 font-semibold';
          } else if (line.startsWith('+')) {
            color = 'text-emerald-300';
            bg = 'rgba(16, 185, 129, 0.12)';
          } else if (line.startsWith('-')) {
            color = 'text-rose-300 line-through';
            bg = 'rgba(244, 63, 94, 0.12)';
          } else if (line.startsWith('@@')) {
            color = 'text-cyan-400 font-semibold';
            bg = 'rgba(6, 182, 212, 0.08)';
          }
          return (
            <div key={idx} style={{ backgroundColor: bg }} className={`${color} px-1.5 rounded-sm whitespace-pre`}>
              {line || ' '}
            </div>
          );
        })}
      </div>
    );
  };

  if (!isSandboxNodeModalOpen) return null;

  const activeAiName =
    llmStatus?.configured_model ||
    (llmStatus?.provider === 'nvidia' ? 'NVIDIA NIM (nemotron-3.5-bolt-e4b)' : 'Local LLM / Fallback');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="w-full max-w-3xl rounded-2xl bg-slate-900 border border-slate-700/90 shadow-2xl flex flex-col max-h-[92vh] overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-bold text-white tracking-wide">
                  Add Sandbox Node &amp; AI Integration
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono font-medium">
                  TASK U8 SANDBOX
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-purple-950/80 border border-purple-500/40 text-[10.5px] font-mono text-purple-200">
                  <Sparkles className="w-3 h-3 text-purple-400 animate-pulse" />
                  <span>Active AI: <strong className="text-purple-100">{activeAiName}</strong></span>
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Create new logic, connect input/output nodes, and let {activeAiName} synthesize endpoints with safeguards.
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              if (batchWirePreview) {
                finalizeBatchWire(batchWirePreview.preview_id, false);
              }
              setIsSandboxNodeModalOpen(false);
            }}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Wizard Steps Indicator */}
        <div className="grid grid-cols-3 border-b border-slate-800 bg-slate-950/40 text-xs font-medium">
          <button
            type="button"
            onClick={() => setStep(1)}
            disabled={step === 3 && isFinalizing}
            className={`py-2.5 px-3 flex items-center justify-center gap-2 transition ${
              step === 1
                ? 'text-emerald-400 border-b-2 border-emerald-500 bg-emerald-950/20 font-bold'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] ${
                step === 1 ? 'bg-emerald-500 text-black font-bold' : 'bg-slate-800 text-slate-400'
              }`}
            >
              1
            </span>
            <span>1. Node &amp; Code</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (name && code) {
                if (selectedInputs.length === 0 && codeNodes.length > 0) {
                  const auto = autoDetectDefaultConnections(name, code, codeNodes);
                  if (auto.inputs.length > 0) setSelectedInputs(auto.inputs);
                  if (selectedOutputs.length === 0 && auto.outputs.length > 0) setSelectedOutputs(auto.outputs);
                }
                setStep(2);
              }
            }}
            disabled={!name || !code || (step === 3 && isFinalizing)}
            className={`py-2.5 px-3 flex items-center justify-center gap-2 transition ${
              step === 2
                ? 'text-sky-400 border-b-2 border-sky-500 bg-sky-950/20 font-bold'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] ${
                step === 2 ? 'bg-sky-500 text-black font-bold' : 'bg-slate-800 text-slate-400'
              }`}
            >
              2
            </span>
            <span>2. Input &amp; Output Connections</span>
          </button>

          <button
            type="button"
            disabled={!batchWirePreview}
            className={`py-2.5 px-3 flex items-center justify-center gap-2 transition ${
              step === 3
                ? 'text-amber-400 border-b-2 border-amber-500 bg-amber-950/20 font-bold'
                : 'text-slate-500 cursor-not-allowed'
            }`}
          >
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] ${
                step === 3 ? 'bg-amber-500 text-black font-bold' : 'bg-slate-800 text-slate-500'
              }`}
            >
              3
            </span>
            <span>3. Review &amp; Finalize</span>
          </button>
        </div>

        {/* Error notification banner */}
        {errorMsg && (
          <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-950/60 border border-rose-500/50 flex items-center gap-2 text-rose-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="flex-1">{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Modal Body / Steps */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
          {/* ================= STEP 1: VS CODE-STYLE WORKSTATION & CODE DEFINITION ================= */}
          {step === 1 && (
            <div className="space-y-3">
              {/* Top Bar: Editor header & Quick Assist Tools */}
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
                    <FileCode2 className="w-4 h-4 text-sky-400" />
                    <span>VS Code Editor</span>
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    Default: {detectedProjectLang.toUpperCase()}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {/* Presets / Templates Toggle */}
                  <button
                    type="button"
                    onClick={() => {
                      setShowPresetsBar(!showPresetsBar);
                      setShowPromptBar(false);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition border cursor-pointer ${
                      showPresetsBar
                        ? 'bg-emerald-950 border-emerald-500 text-emerald-300 shadow-sm'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>📦 Component Templates</span>
                  </button>

                  {/* AI Scaffold Generator Toggle */}
                  <button
                    type="button"
                    onClick={() => {
                      setShowPromptBar(!showPromptBar);
                      setShowPresetsBar(false);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition border cursor-pointer ${
                      showPromptBar
                        ? 'bg-sky-950 border-sky-500 text-sky-300 shadow-sm'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Wand2 className="w-3.5 h-3.5 text-amber-300" />
                    <span>✨ AI Scaffold</span>
                  </button>
                </div>
              </div>

              {/* Collapsible Drawer 1: AI Prompt Scaffolding */}
              {showPromptBar && (
                <div className="p-3.5 rounded-xl bg-slate-950/90 border border-sky-800/50 space-y-2.5 shadow-lg">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-sky-300 flex items-center gap-1.5 text-xs">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      Describe the node logic for {activeAiName}:
                    </label>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 border border-purple-500/40 text-purple-300">
                      ⚡ {activeAiName}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={taskPrompt}
                      onChange={(e) => setTaskPrompt(e.target.value)}
                      placeholder="e.g. Build a Redis rate limiter that blocks brute-force requests and caches quotas"
                      className="flex-1 rounded-lg bg-slate-900 border border-slate-700 p-2 text-slate-100 placeholder:text-slate-500 focus:border-sky-500 outline-none text-xs font-mono"
                    />
                    <button
                      type="button"
                      disabled={isGeneratingAi || !taskPrompt.trim()}
                      onClick={handleGenerateFromAi}
                      className="px-3.5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold flex items-center gap-1.5 text-xs shrink-0 disabled:opacity-50 transition cursor-pointer"
                    >
                      {isGeneratingAi ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Synthesizing...
                        </>
                      ) : (
                        <>
                          <Wand2 className="w-3.5 h-3.5 text-amber-300" /> Generate with AI
                        </>
                      )}
                    </button>
                  </div>
                  {aiExplanation && (
                    <div className="p-2 rounded bg-sky-950/40 border border-sky-800/40 text-[11px] text-sky-200">
                      <strong className="text-sky-300">AI Plan: </strong>
                      {aiExplanation}
                    </div>
                  )}
                </div>
              )}

              {/* Collapsible Drawer 2: 1-Click Component Templates */}
              {showPresetsBar && (
                <div className="p-3 rounded-xl bg-slate-950/90 border border-slate-800 space-y-2 shadow-lg">
                  <div className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
                    <span>⚡ Choose Starter Template ({lang.toUpperCase()}):</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {activePresets.map((p) => (
                      <button
                        key={p.name}
                        type="button"
                        onClick={() => {
                          handleApplyPreset(p);
                          setShowPresetsBar(false);
                        }}
                        className="p-2 rounded-lg text-left border border-slate-800 bg-slate-900/80 hover:border-emerald-500 hover:bg-slate-900 transition flex items-center justify-between cursor-pointer"
                      >
                        <div className="min-w-0 pr-2">
                          <div className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
                            <span>{p.icon}</span>
                            <span className="truncate">{p.label}</span>
                          </div>
                          <div className="text-[10px] text-cyan-400 font-mono truncate">{p.name}</div>
                        </div>
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 uppercase shrink-0">
                          {p.lang}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Interactive AI Architecture Questions / Conflict Advisor */}
              {clarificationQuestions.length > 0 && (
                <div className="p-4 rounded-xl bg-gradient-to-br from-amber-950/70 via-slate-900 to-slate-950 border-2 border-amber-500/70 shadow-2xl space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400 animate-pulse" />
                      <h4 className="font-bold text-amber-300 text-xs tracking-wide uppercase">
                        AI Architecture Advisor — Clarification Needed
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 border border-amber-500/30 font-semibold">
                      Conflict Detected
                    </span>
                  </div>

                  <p className="text-[11.5px] text-slate-300 leading-relaxed">
                    The AI analyzed your project architecture and found potential issues with your configuration. Please select an action so the code runs cleanly without import errors:
                  </p>

                  <div className="space-y-3">
                    {clarificationQuestions.map((q) => (
                      <div key={q.id} className="p-3 rounded-lg bg-slate-950/80 border border-amber-500/40 space-y-2">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <strong className="text-white text-xs block">{q.title}</strong>
                            <p className="text-[11px] text-amber-200/90 mt-0.5">{q.question}</p>
                            <p className="text-[10.5px] text-slate-400 mt-1 italic">{q.reason}</p>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-slate-800 space-y-1.5">
                          <span className="text-[10px] text-slate-400 font-semibold block">Choose how to resolve:</span>
                          <div className="grid grid-cols-1 gap-1.5">
                            {q.options.map((opt) => (
                              <button
                                key={opt.id}
                                type="button"
                                onClick={() => handleApplyClarificationOption(q.id, opt)}
                                className={`p-2 rounded-lg text-left border text-xs transition flex items-center justify-between cursor-pointer ${
                                  opt.is_recommended
                                    ? 'bg-emerald-950/60 border-emerald-500/80 text-emerald-200 hover:bg-emerald-950 shadow-sm'
                                    : 'bg-slate-900 border-slate-700/80 text-slate-300 hover:bg-slate-850 hover:border-slate-600'
                                }`}
                              >
                                <div className="min-w-0 pr-2">
                                  <div className="font-bold flex items-center gap-1.5">
                                    {opt.is_recommended && <span className="text-emerald-400">★</span>}
                                    <span>{opt.title}</span>
                                  </div>
                                  <p className="text-[10.5px] text-slate-400 mt-0.5">{opt.description}</p>
                                </div>
                                {opt.is_recommended && (
                                  <span className="text-[9.5px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold shrink-0">
                                    Recommended
                                  </span>
                                )}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Real VS Code Editor Window */}
              <div className="rounded-xl border border-[#333333] bg-[#1e1e1e] overflow-hidden shadow-2xl flex flex-col">
                {/* VS Code Tab Bar & Controls */}
                <div className="flex items-center justify-between bg-[#252526] border-b border-[#333333] px-2 pt-1.5">
                  {/* Left: Active Tab with editable filename */}
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e1e1e] border-t-2 border-t-sky-400 border-x border-[#333333] rounded-t-md text-xs font-mono text-slate-200 shadow-inner">
                      <FileCode2 className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="path/to/module.py"
                        className="bg-transparent border-none outline-none font-mono text-xs text-white placeholder:text-slate-500 w-48 sm:w-64"
                        title="Edit node file path"
                      />
                    </div>
                  </div>

                  {/* Right: Language Selector & Crown Jewel quick toggle */}
                  <div className="flex items-center gap-2.5 pb-1">
                    <div className="flex items-center gap-1.5 bg-[#1e1e1e] border border-[#3c3c3c] rounded px-2 py-0.5">
                      <span className="text-[10px] font-mono text-slate-400">Language:</span>
                      <select
                        value={lang}
                        onChange={(e) => handleLanguageChange(e.target.value as ProjectLang)}
                        className="bg-transparent border-none text-slate-200 font-mono text-xs focus:outline-none cursor-pointer"
                      >
                        <option value="py">Python (.py)</option>
                        <option value="ts">TypeScript (.ts)</option>
                        <option value="tsx">TypeScript React (.tsx)</option>
                        <option value="js">JavaScript (.js)</option>
                        <option value="jsx">JavaScript React (.jsx)</option>
                      </select>
                    </div>

                    <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 text-xs px-2 py-0.5 rounded bg-[#1e1e1e] border border-[#3c3c3c] hover:border-amber-400/50">
                      <input
                        type="checkbox"
                        checked={isCrown}
                        onChange={(e) => setIsCrown(e.target.checked)}
                        className="accent-amber-400 w-3.5 h-3.5 rounded cursor-pointer"
                      />
                      <Crown className="w-3.5 h-3.5 text-amber-400" />
                      <span className="text-[11px] font-medium text-amber-300">Crown Jewel</span>
                    </label>
                  </div>
                </div>

                {/* VS Code Canvas (Line numbers gutter + Code Area) */}
                <div className="flex min-h-[260px] max-h-[360px] bg-[#1e1e1e] overflow-hidden">
                  {/* Line Numbers Gutter */}
                  <div className="select-none py-3 px-3 bg-[#1e1e1e] border-r border-[#333333] text-right font-mono text-[11px] text-[#858585] leading-[1.35rem] min-w-[42px] overflow-hidden">
                    {lineNumbers.map((num) => (
                      <div key={num} className="leading-[1.35rem]">
                        {num}
                      </div>
                    ))}
                  </div>

                  {/* Source Code Textarea */}
                  <textarea
                    rows={12}
                    value={code}
                    onChange={(e) => {
                      setCode(e.target.value);
                      if (validationResult) setValidationResult(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Tab') {
                        e.preventDefault();
                        const target = e.currentTarget;
                        const start = target.selectionStart;
                        const end = target.selectionEnd;
                        const val = target.value;
                        const indent = '    ';
                        setCode(val.substring(0, start) + indent + val.substring(end));
                        setTimeout(() => {
                          target.selectionStart = target.selectionEnd = start + indent.length;
                        }, 0);
                      }
                    }}
                    placeholder="# Write or paste your node logic here..."
                    spellCheck={false}
                    className="flex-1 bg-[#1e1e1e] text-[#d4d4d4] p-3 font-mono text-[12px] leading-[1.35rem] border-none outline-none resize-none focus:ring-0 overflow-y-auto selection:bg-[#264f78]"
                  />
                </div>

                {/* Error Banner with Auto-Fix (if syntax error exists) */}
                {validationResult && !validationResult.is_valid && (
                  <div className="bg-rose-950/90 border-t border-rose-500/50 p-2.5 px-4 flex items-center justify-between gap-3 text-xs text-rose-200">
                    <div className="flex items-center gap-2 min-w-0">
                      <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                      <span className="font-mono truncate">{validationResult.error}</span>
                    </div>
                    <button
                      type="button"
                      disabled={isValidating}
                      onClick={handleAutoFixError}
                      className="px-3 py-1 rounded-md bg-amber-500 hover:bg-amber-400 text-black font-bold flex items-center gap-1.5 transition text-xs shadow-md shrink-0 cursor-pointer"
                    >
                      {isValidating ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Wand2 className="w-3.5 h-3.5 text-black" />
                      )}
                      <span>🔧 Auto-Fix with AI</span>
                    </button>
                  </div>
                )}

                {/* Success Banner (if valid) */}
                {validationResult && validationResult.is_valid && (
                  <div className="bg-emerald-950/80 border-t border-emerald-500/50 p-2 px-4 flex items-center justify-between text-xs text-emerald-200">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span className="font-mono">
                        {validationResult.ai_validation_summary || '✓ Syntax & AST validated with 0 errors by NVIDIA NIM'}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-300 border border-emerald-500/30">
                      Valid {lang.toUpperCase()}
                    </span>
                  </div>
                )}

                {/* VS Code Bottom Status Bar */}
                <div className="bg-[#007acc] text-white px-3 py-1 flex items-center justify-between text-[11px] font-sans font-medium select-none">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <span className="opacity-80">Lines:</span>
                      <strong>{lineNumbers.length}</strong>
                    </span>
                    <span className="opacity-75">|</span>
                    <span>Spaces: 4</span>
                    <span className="opacity-75">|</span>
                    <span>UTF-8</span>
                    <span className="opacity-75">|</span>
                    <span className="uppercase font-mono">{lang}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="opacity-90 font-mono text-[10px]">
                      ⚡ {activeAiName}
                    </span>
                  </div>
                </div>
              </div>

              {/* Bottom Action Footer */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsSandboxNodeModalOpen(false)}
                  className="px-3.5 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-900/80 hover:bg-slate-800 transition text-xs"
                >
                  Cancel
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleProceedToConnections}
                    className="px-3.5 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-900/80 hover:bg-slate-800 transition text-xs"
                  >
                    Manual Wiring →
                  </button>

                  <button
                    type="button"
                    disabled={isValidating || !code.trim() || !name.trim()}
                    onClick={handleValidateAndAutoConnect}
                    className="px-5 py-2.5 rounded-xl font-bold text-white bg-gradient-to-r from-emerald-600 via-teal-600 to-sky-600 hover:brightness-110 shadow-lg flex items-center gap-2 text-xs disabled:opacity-50 transition cursor-pointer"
                  >
                    {isValidating ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-amber-300" />
                        <span>AI Inspecting Errors &amp; Auto-Connecting...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 text-amber-300" />
                        <span>⚡ Validate Code &amp; Auto-Connect with AI →</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 2: INPUT & OUTPUT CONNECTIONS ================= */}
          {step === 2 && (
            <div className="space-y-4">
              {/* Validation Result Banner */}
              {validationResult?.is_valid && (
                <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/50 flex items-center justify-between gap-3 text-xs text-emerald-200">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    <div>
                      <div className="font-bold text-emerald-300 flex items-center gap-2">
                        <span>Code Validated &amp; Connected by AI</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 border border-purple-500/40 text-purple-300">
                          ⚡ {validationResult.provider || activeAiName}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-300 mt-0.5">
                        {validationResult.ai_validation_summary || '0 errors detected. Caller entry points and dependencies have been automatically selected.'}
                      </p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-300 border border-emerald-500/30">
                    AST Clean
                  </span>
                </div>
              )}

              <div className="p-3.5 rounded-xl bg-slate-950/90 border border-slate-800 flex items-center justify-between gap-3 flex-wrap">
                <div className="space-y-0.5 max-w-[70%]">
                  <div className="font-bold text-white flex items-center gap-2 text-xs">
                    <Network className="w-4 h-4 text-sky-400" /> Configure Graph Connections for{' '}
                    <span className="font-mono text-emerald-400">{name}</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Existing project files were analyzed. Caller entry points and dependencies are auto-detected below.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleReAutoSelect}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-950/80 hover:bg-sky-900 border border-sky-500/50 text-sky-200 text-xs font-mono font-medium transition cursor-pointer shadow-sm"
                  title="Re-run architectural heuristic to automatically choose the best caller and dependency nodes"
                >
                  <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                  <span>⚡ Auto-Select Best</span>
                </button>
              </div>

              {/* Input Connections Panel */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-bold text-slate-200 flex items-center gap-1.5 text-xs">
                      <span className="w-2.5 h-2.5 rounded-full bg-sky-400 inline-block" />
                      1. Input Connections (Callers → {name})
                    </span>
                    <p className="text-[11px] text-slate-400">
                      Existing nodes that will be modified to import and call this new node.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800 text-xs">
                    <span className="text-slate-400">Connections:</span>
                    <span className="font-mono font-bold text-sky-400">{selectedInputs.length}</span>
                  </div>
                </div>

                <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                  {sortedAvailableNodes.map((nodeId) => {
                    const isSelected = selectedInputs.includes(nodeId);
                    const isCode = isCodeFile(nodeId);
                    const isServer = /server\.|app\.|main\.|index\./i.test(nodeId);
                    return (
                      <div
                        key={`in-${nodeId}`}
                        onClick={() => handleToggleInputNode(nodeId)}
                        className={`p-2 rounded-lg border flex items-center justify-between cursor-pointer transition ${
                          isSelected
                            ? 'bg-sky-950/40 border-sky-500/70 text-sky-200 shadow-sm'
                            : 'bg-slate-900/60 border-slate-800/80 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="accent-sky-400 rounded cursor-pointer"
                          />
                          <span className={`font-mono text-xs truncate ${isSelected ? 'font-bold text-white' : 'text-slate-300'}`}>
                            {nodeId}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                          {isServer && (
                            <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/50 text-cyan-300 font-mono">
                              ★ Server Entry
                            </span>
                          )}
                          {!isCode && (
                            <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-500 font-mono">
                              Config
                            </span>
                          )}
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                            Caller
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Output Connections Panel */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-bold text-slate-200 flex items-center gap-1.5 text-xs">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
                      2. Output Connections ({name} → Dependencies)
                    </span>
                    <p className="text-[11px] text-slate-400">
                      Existing nodes that this new node will import and invoke as dependencies.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800 text-xs">
                    <span className="text-slate-400">Connections:</span>
                    <span className="font-mono font-bold text-emerald-400">{selectedOutputs.length}</span>
                  </div>
                </div>

                <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                  {sortedAvailableNodes.map((nodeId) => {
                    const isSelected = selectedOutputs.includes(nodeId);
                    const isCode = isCodeFile(nodeId);
                    const isDbOrCache = /redis|cache|db|sql|postgres|mongo|database/i.test(nodeId);
                    return (
                      <div
                        key={`out-${nodeId}`}
                        onClick={() => handleToggleOutputNode(nodeId)}
                        className={`p-2 rounded-lg border flex items-center justify-between cursor-pointer transition ${
                          isSelected
                            ? 'bg-emerald-950/40 border-emerald-500/70 text-emerald-200 shadow-sm'
                            : 'bg-slate-900/60 border-slate-800/80 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="accent-emerald-400 rounded cursor-pointer"
                          />
                          <span className={`font-mono text-xs truncate ${isSelected ? 'font-bold text-white' : 'text-slate-300'}`}>
                            {nodeId}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                          {isDbOrCache && (
                            <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 font-mono">
                              ★ DB / Cache
                            </span>
                          )}
                          {!isCode && (
                            <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-500 font-mono">
                              Config
                            </span>
                          )}
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                            Dependency
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Navigation Actions */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="px-3.5 py-2 rounded-lg text-slate-400 hover:text-white bg-slate-900 flex items-center gap-1.5"
                >
                  <ArrowLeft className="w-4 h-4" /> Back to Code
                </button>

                <button
                  type="button"
                  disabled={isBatchWiring}
                  onClick={handleSynthesizeBatchWire}
                  className="px-5 py-2 rounded-lg font-bold text-white bg-gradient-to-r from-sky-600 via-indigo-600 to-emerald-600 hover:brightness-110 shadow-lg flex items-center gap-2 disabled:opacity-50"
                >
                  {isBatchWiring ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin text-amber-300" />
                      Synthesizing Endpoint Integrations with AI...
                    </>
                  ) : batchWirePreview ? (
                    <>
                      <Wand2 className="w-4 h-4 text-amber-300" />
                      Review AI Wiring Diff ({batchWirePreview.connected_changes?.length || 0} modified) →
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-4 h-4 text-amber-300" />
                      Synthesize AI Wiring &amp; Preview Changes →
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* ================= STEP 3: DIFF REVIEW & FINALIZE DECISION ================= */}
          {step === 3 && batchWirePreview && (
            <div className="space-y-4">
              {/* Safeguard Alert Notice */}
              <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 flex items-start gap-3">
                <Shield className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-emerald-300 text-xs flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5" /> Safe Preview Mode: Files on disk have NOT been modified yet.
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    Review the AI-synthesized code additions below. Choose whether to <strong>Finalize &amp; Save</strong> (which
                    writes changes into project files and reflects live in your runtime), or <strong>Discard</strong> to exit
                    safely without modifying any code.
                  </p>
                </div>
              </div>

              {/* 1. New Node to be Created */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 flex items-center gap-1.5 text-xs">
                    <FileCode2 className="w-4 h-4 text-emerald-400" />
                    New Node File to Create:
                    <span className="font-mono text-emerald-400 ml-1">{batchWirePreview.new_node.name}</span>
                  </span>
                  <div className="flex items-center gap-2">
                    {batchWirePreview.new_node.is_crown_jewel && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 flex items-center gap-1">
                        <Crown className="w-3 h-3" /> Crown Jewel
                      </span>
                    )}
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                      {batchWirePreview.new_node.code.split('\n').length} lines
                    </span>
                  </div>
                </div>

                <div className="font-mono text-[11px] bg-[#030712] p-3 rounded-lg border border-slate-800/80 max-h-36 overflow-y-auto text-slate-300">
                  <pre>{batchWirePreview.new_node.code}</pre>
                </div>
              </div>

              {/* 2. Connected Nodes Code Changes & Diff Preview */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-200 text-xs flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-sky-400" />
                    Synthesized Changes to Connected Nodes ({batchWirePreview.connected_changes.length} files)
                  </h3>
                  <span className="text-[11px] text-slate-400 font-mono">Unified Diff Preview</span>
                </div>

                {batchWirePreview.connected_changes.length === 0 ? (
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-center text-slate-400 text-xs">
                    No connected files selected. Only the new node will be created.
                  </div>
                ) : (
                  batchWirePreview.connected_changes.map((change, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              change.direction === 'input' ? 'bg-sky-400' : 'bg-emerald-400'
                            }`}
                          />
                          <span className="font-mono font-bold text-slate-200 text-xs">{change.node_id}</span>
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded ${
                              change.direction === 'input'
                                ? 'bg-sky-500/20 text-sky-300'
                                : 'bg-emerald-500/20 text-emerald-300'
                            }`}
                          >
                            {change.direction === 'input' ? 'Caller Integration' : 'Dependency Wiring'}
                          </span>
                        </div>
                      </div>

                      {/* Endpoint Signature & Rationale */}
                      <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] space-y-1">
                        <div className="text-slate-300">
                          <strong className="text-sky-300 font-mono">Endpoint:</strong> {change.endpoint}
                        </div>
                        <div className="text-slate-400">
                          <strong className="text-slate-300">Rationale:</strong> {change.rationale}
                        </div>
                      </div>

                      {/* Unified Diff */}
                      <div>
                        <div className="text-[10px] text-slate-400 font-semibold mb-1">Proposed Code Diff:</div>
                        {renderUnifiedDiff(change.patch)}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Action Buttons: Finalize vs Discard */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-800">
                <button
                  type="button"
                  disabled={isFinalizing}
                  onClick={() => handleFinalizeDecision(false)}
                  className="px-4 py-2 rounded-lg text-rose-300 hover:text-white bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/40 font-semibold flex items-center gap-1.5 transition text-xs disabled:opacity-50"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Discard &amp; Don't Change Code
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={isFinalizing}
                    onClick={() => setStep(2)}
                    className="px-3.5 py-2 rounded-lg text-slate-400 hover:text-white bg-slate-900 flex items-center gap-1.5 text-xs"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> Back / Edit
                  </button>

                  <button
                    type="button"
                    disabled={isFinalizing}
                    onClick={() => handleFinalizeDecision(true)}
                    className="px-5 py-2 rounded-lg font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-950/50 flex items-center gap-2 text-xs transition disabled:opacity-50"
                  >
                    {isFinalizing ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-white" />
                        Writing Changes to Disk...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-white" />
                        Finalize &amp; Save Changes to Project
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
