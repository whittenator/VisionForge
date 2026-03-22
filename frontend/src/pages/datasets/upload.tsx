import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import Select from '@/components/ui/Select';
import { apiGet, apiPost } from '@/services/api';

interface UploadEntry {
  name: string;
  progress: number;
  status: 'pending' | 'uploading' | 'done' | 'error';
  error?: string;
}

interface Project { id: string; name: string; }

export default function DatasetUpload() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [projectId, setProjectId]   = useState(searchParams.get('projectId') || '');
  const [datasetId, setDatasetId]   = useState(searchParams.get('datasetId') || '');
  const [versionId, setVersionId]   = useState(searchParams.get('versionId') || '');

  // Dataset creation state (only shown when no datasetId/versionId provided)
  const [projects, setProjects]           = useState<Project[]>([]);
  const [newDatasetName, setNewDatasetName] = useState('');
  const [creating, setCreating]            = useState(false);
  const [createError, setCreateError]      = useState<string | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allDone, setAllDone] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load projects for the creation form
  useEffect(() => {
    if (!datasetId) {
      apiGet<Project[]>('/api/projects').then(setProjects).catch(console.error);
    }
  }, [datasetId]);

  async function createDatasetAndVersion() {
    if (!newDatasetName.trim()) { setCreateError('Enter a dataset name'); return; }
    const effectiveProject = projectId;
    if (!effectiveProject) { setCreateError('Select a project'); return; }
    setCreating(true);
    setCreateError(null);
    try {
      const ds = await apiPost<{ id: string; activeVersionId: string }>(
        `/api/datasets/${effectiveProject}`,
        { name: newDatasetName.trim() }
      );
      setDatasetId(ds.id);
      setVersionId(ds.activeVersionId);
      // Update URL params so the user can share/reload
      setSearchParams({
        ...(effectiveProject ? { projectId: effectiveProject } : {}),
        datasetId: ds.id,
        versionId: ds.activeVersionId,
      });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create dataset');
    } finally {
      setCreating(false);
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []);
    setFiles(selected);
    setUploads([]);
    setAllDone(false);
    setError(null);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(dropped);
    setUploads([]);
    setAllDone(false);
    setError(null);
  }

  function onDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
  }

  async function onUpload() {
    if (!files.length) return;
    if (!datasetId || !versionId) {
      setError('Create a dataset first before uploading.');
      return;
    }
    setUploading(true);
    setError(null);
    setAllDone(false);

    const initial: UploadEntry[] = files.map((f) => ({ name: f.name, progress: 0, status: 'pending' }));
    setUploads(initial);

    let hasError = false;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploads((prev) => prev.map((u, idx) => (idx === i ? { ...u, status: 'uploading' } : u)));

      try {
        const { url, objectKey } = await apiPost<{
          url: string;
          fields: Record<string, string>;
          objectKey: string;
        }>('/api/ingest/upload-url', {
          datasetVersionId: versionId,
          filename: file.name,
          contentType: file.type,
        });

        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const pct = Math.round((e.loaded / e.total) * 100);
              setUploads((prev) => prev.map((u, idx) => (idx === i ? { ...u, progress: pct } : u)));
            }
          };
          xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new Error(`Upload failed: ${xhr.status}`)));
          xhr.onerror = () => reject(new Error('Network error during upload'));
          xhr.open('PUT', url);
          xhr.setRequestHeader('Content-Type', file.type);
          xhr.send(file);
        });

        await apiPost('/api/ingest/confirm', {
          dataset_id: datasetId,
          version_id: versionId,
          storage_key: objectKey,
          filename: file.name,
          content_type: file.type,
        });

        setUploads((prev) => prev.map((u, idx) => (idx === i ? { ...u, progress: 100, status: 'done' } : u)));
      } catch (err) {
        hasError = true;
        const msg = err instanceof Error ? err.message : 'Upload failed';
        setUploads((prev) => prev.map((u, idx) => (idx === i ? { ...u, status: 'error', error: msg } : u)));
        setError(msg);
      }
    }

    setUploading(false);
    if (!hasError) setAllDone(true);
  }

  const doneCount = uploads.filter((u) => u.status === 'done').length;

  return (
    <div className="max-w-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Datasets / Upload</div>
          <h1>Upload Dataset Assets</h1>
        </div>
        {projectId && (
          <Link className="text-xs font-mono text-[var(--hud-accent)] hover:underline" to={`/projects/${projectId}`}>
            ← BACK TO PROJECT
          </Link>
        )}
      </div>

      {/* Dataset creation form — shown when no datasetId/versionId in URL */}
      {(!datasetId || !versionId) && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="label-overline">Create New Dataset</span>
          </div>
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-overline block mb-1" htmlFor="proj-select">Project</label>
                <Select
                  id="proj-select"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                >
                  <option value="">— select —</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </div>
              <div>
                <label className="label-overline block mb-1" htmlFor="ds-name">Dataset Name</label>
                <Input
                  id="ds-name"
                  placeholder="e.g. Detection v1"
                  value={newDatasetName}
                  onChange={(e) => setNewDatasetName(e.target.value)}
                  onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && createDatasetAndVersion()}
                />
              </div>
            </div>
            {createError && <Alert variant="error">{createError}</Alert>}
            <Button onClick={createDatasetAndVersion} disabled={creating || !newDatasetName.trim() || !projectId}>
              {creating ? <span className="flex items-center gap-2"><Spinner size={12} />Creating…</span> : 'Create Dataset & Continue'}
            </Button>
          </div>
        </div>
      )}

      {/* Context info — shown once dataset/version is known */}
      {datasetId && versionId && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-2 flex items-center gap-4 text-xs font-mono">
          <span>
            <span className="text-[var(--hud-text-muted)]">DATASET </span>
            <span className="text-[var(--hud-text-data)]">{datasetId.slice(0, 12)}…</span>
          </span>
          <span>
            <span className="text-[var(--hud-text-muted)]">VERSION </span>
            <span className="text-[var(--hud-text-data)]">{versionId.slice(0, 12)}…</span>
          </span>
          <Link
            to={`/datasets/${datasetId}`}
            className="ml-auto text-[var(--hud-accent)] hover:underline underline-offset-2"
          >
            VIEW DATASET →
          </Link>
        </div>
      )}

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onClick={() => fileInputRef.current?.click()}
        className="flex flex-col items-center justify-center border border-dashed border-[var(--hud-border-strong)] bg-[var(--hud-inset)] p-10 cursor-pointer hover:border-[var(--hud-accent)] hover:bg-[var(--hud-elevated)] transition-colors group"
      >
        <div className="mb-3 text-[var(--hud-text-muted)] group-hover:text-[var(--hud-accent)] transition-colors">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <p className="text-sm font-medium text-[var(--hud-text-secondary)]">
          Drop files here or click to browse
        </p>
        <p className="text-xs font-mono text-[var(--hud-text-muted)] mt-1">
          Images · Videos · Annotation files
        </p>
        <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onFileChange} />
      </div>

      {/* File count */}
      {files.length > 0 && uploads.length === 0 && (
        <div className="text-xs font-mono text-[var(--hud-text-secondary)]">
          <span className="text-[var(--hud-accent)]">{files.length}</span> file(s) selected
        </div>
      )}

      {/* Progress list */}
      {uploads.length > 0 && (
        <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
          {uploads.map((u, i) => (
            <div key={i} className="px-3 py-2 space-y-1.5">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="truncate max-w-xs text-[var(--hud-text-secondary)]">{u.name}</span>
                <span
                  className={
                    u.status === 'done'  ? 'text-[var(--hud-success-text)]' :
                    u.status === 'error' ? 'text-[var(--hud-danger-text)]' :
                    'text-[var(--hud-text-muted)]'
                  }
                >
                  {u.status === 'done'     ? '✓ DONE'        :
                   u.status === 'error'    ? '✗ ERROR'       :
                   u.status === 'uploading'? `${u.progress}%` :
                   'PENDING'}
                </span>
              </div>
              <div className="h-0.5 w-full bg-[var(--hud-inset)] overflow-hidden">
                <div
                  style={{ width: `${u.progress}%` }}
                  className={`h-full transition-all ${u.status === 'error' ? 'bg-[var(--hud-danger)]' : 'bg-[var(--hud-accent)]'}`}
                />
              </div>
              {u.error && (
                <p className="text-[0.6875rem] font-mono text-[var(--hud-danger-text)]">{u.error}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {error && <Alert variant="error">{error}</Alert>}

      <div className="flex items-center gap-3">
        <Button
          onClick={onUpload}
          disabled={files.length === 0 || uploading || !datasetId || !versionId}
        >
          {uploading ? (
            <span className="flex items-center gap-2">
              <Spinner size={12} />
              Uploading {doneCount}/{files.length}…
            </span>
          ) : (
            `Upload ${files.length > 0 ? `${files.length} file(s)` : ''}`
          )}
        </Button>

        {allDone && (
          <span className="text-xs font-mono text-[var(--hud-success-text)]">
            ✓ {doneCount} file(s) uploaded
          </span>
        )}
      </div>

      {allDone && datasetId && (
        <div className="flex gap-2 pt-1">
          {projectId && (
            <Button variant="outline" size="sm" as="a">
              <Link to={`/projects/${projectId}`}>Go to Project</Link>
            </Button>
          )}
          <Button variant="outline" size="sm" as="a">
            <Link to={`/datasets/version?datasetId=${datasetId}`}>Create Snapshot →</Link>
          </Button>
        </div>
      )}
    </div>
  );
}
