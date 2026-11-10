import React, { useState, useRef } from 'react';
import {
  X,
  FolderOpen,
  GitBranch,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

const BINARY_EXTENSIONS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
  '.woff', '.woff2', '.ttf', '.eot', '.otf',
  '.mp3', '.mp4', '.wav', '.ogg', '.webm',
  '.pdf', '.zip', '.gz', '.tar', '.db', '.sqlite', '.sqlite3',
]);

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const res = String(reader.result || '');
      const b64 = res.includes(',') ? res.split(',', 2)[1] : res;
      resolve(b64);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export const OpenProjectModal: React.FC = () => {
  const {
    isOpenProjectModalOpen,
    setIsOpenProjectModalOpen,
    openProject,
    uploadProjectFolder,
    projects,
    projectId,
    fetchInitialWorkspace,
    isLoadingProject,
    errorBanner,
  } = useReleaseStore();

  const [tab, setTab] = useState<'local' | 'github' | 'upload'>('local');
  const [localPath, setLocalPath] = useState('demo');
  const [githubUrl, setGitBranchUrl] = useState('https://github.com/tiangolo/full-stack-fastapi-template');
  const [githubBranch, setGitBranchBranch] = useState('');
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpenProjectModalOpen) return null;

  const handleFolderPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const skipDirs = ['node_modules/', '.git/', '.venv/', 'venv/', '__pycache__/', 'dist/', 'build/'];
    const uploaded: { path: string; content: string; is_base64: boolean }[] = [];
    let folderName = 'uploaded_project';

    setUploadStatus(`Reading ${fileList.length} files (preserving binary assets & styles)...`);
    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i];
      const rel = (f as any).webkitRelativePath || f.name;
      if (i === 0 && rel.includes('/')) {
        folderName = rel.split('/')[0];
      }
      if (skipDirs.some((sk) => rel.includes(sk))) continue;
      if (f.size > 2_500_000) continue;

      const subPath = rel.includes('/') ? rel.split('/').slice(1).join('/') : rel;
      const dotIdx = subPath.lastIndexOf('.');
      const ext = dotIdx >= 0 ? subPath.slice(dotIdx).toLowerCase() : '';
      const isBinary = BINARY_EXTENSIONS.has(ext);

      try {
        if (isBinary) {
          const b64 = await readFileAsBase64(f);
          uploaded.push({ path: subPath, content: b64, is_base64: true });
        } else {
          const text = await f.text();
          uploaded.push({ path: subPath, content: text, is_base64: false });
        }
      } catch {
        // skip unreadable file
      }
      if (uploaded.length >= 500) break;
    }

    setUploadStatus(`Uploading ${uploaded.length} source & asset files into isolated sandbox...`);
    const ok = await uploadProjectFolder(folderName, uploaded);
    if (ok) {
      setUploadStatus(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl rounded-2xl bg-slate-900 border border-slate-700/90 p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-sky-500/20 text-sky-400">
              <FolderOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Open Local Folder or GitHub Repo</h2>
              <p className="text-xs text-slate-400">
                Detects framework &amp; styling architecture, builds AST graph, and scores release risk.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpenProjectModalOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Tabs */}
        <div className="flex rounded-xl bg-slate-950 p-1 border border-slate-800 text-xs font-semibold">
          <button
            onClick={() => setTab('local')}
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
              tab === 'local' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            <FolderOpen className="w-3.5 h-3.5" /> Local Path / Recent
          </button>
          <button
            onClick={() => setTab('upload')}
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
              tab === 'upload' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            <UploadCloud className="w-3.5 h-3.5" /> Drop Local Folder
          </button>
          <button
            onClick={() => setTab('github')}
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
              tab === 'github' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" /> Clone GitHub URL
          </button>
        </div>

        {errorBanner && (
          <div className="p-3 rounded-xl bg-red-950/50 border border-red-600/60 text-xs text-red-200 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorBanner}</span>
          </div>
        )}

        {tab === 'local' && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              await openProject('local', localPath);
            }}
            className="space-y-3 text-xs"
          >
            <div>
              <label className="text-slate-300 font-semibold block mb-1">
                Local Folder Path or Project ID
              </label>
              <input
                type="text"
                value={localPath}
                onChange={(e) => setLocalPath(e.target.value)}
                placeholder="e.g., demo or C:\Users\you\projects\my-fastapi-app"
                className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 font-mono text-slate-100 focus:border-sky-500 outline-none"
              />
            </div>

            <div>
              <div className="text-[11px] font-semibold text-slate-400 mb-1.5">
                Recent / Registered Sandbox Projects:
              </div>
              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {projects.map((p) => {
                  const id = p.project_id || (p as any).pid || '';
                  return (
                    <div
                      key={id}
                      onClick={async () => {
                        await fetchInitialWorkspace(id);
                        setIsOpenProjectModalOpen(false);
                      }}
                      className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer transition ${
                        id === projectId
                          ? 'bg-sky-950/40 border-sky-500/60 text-sky-200'
                          : 'bg-slate-950 border-slate-800 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="font-mono font-bold text-xs flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          {p.name || id}
                        </div>
                        <div className="text-[10.5px] font-mono text-slate-500 truncate">{p.path}</div>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] font-mono text-sky-300">
                        {p.runtime || (p as any).stack || 'py'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="submit"
                disabled={isLoadingProject}
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold flex items-center gap-1.5 shadow disabled:opacity-50"
              >
                {isLoadingProject && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Open &amp; Build Graph
              </button>
            </div>
          </form>
        )}

        {tab === 'upload' && (
          <div className="space-y-3 text-xs">
            <div
              onClick={() => folderInputRef.current?.click()}
              className="border-2 border-dashed border-emerald-500/50 hover:border-emerald-400 rounded-2xl p-8 text-center cursor-pointer bg-slate-950/80 hover:bg-slate-900/80 transition space-y-2"
            >
              <UploadCloud className="w-10 h-10 text-emerald-400 mx-auto" />
              <div className="text-sm font-bold text-slate-100">
                Click to Select a Project Folder from Your Computer
              </div>
              <p className="text-[11px] text-slate-400 max-w-md mx-auto">
                Copies source files and binary assets (PNG, SVG, ICO, fonts, SQLite) into an isolated Release Domino workspace without modifying your host files.
              </p>
              <input
                ref={folderInputRef}
                type="file"
                {...({ webkitdirectory: '', directory: '' } as any)}
                multiple
                onChange={handleFolderPick}
                className="hidden"
              />
            </div>
            {uploadStatus && (
              <div className="text-center font-mono text-emerald-300 text-xs">{uploadStatus}</div>
            )}
          </div>
        )}

        {tab === 'github' && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              await openProject('github', githubUrl, githubBranch || undefined);
            }}
            className="space-y-3 text-xs"
          >
            <div>
              <label className="text-slate-300 font-semibold block mb-1">GitHub Repository URL</label>
              <input
                type="text"
                value={githubUrl}
                onChange={(e) => setGitBranchUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 font-mono text-slate-100 focus:border-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">Branch (Optional)</label>
              <input
                type="text"
                value={githubBranch}
                onChange={(e) => setGitBranchBranch(e.target.value)}
                placeholder="main"
                className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 font-mono text-slate-100 focus:border-indigo-500 outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="submit"
                disabled={isLoadingProject}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold flex items-center gap-1.5 shadow disabled:opacity-50"
              >
                {isLoadingProject && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Clone &amp; Analyze Repo
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
