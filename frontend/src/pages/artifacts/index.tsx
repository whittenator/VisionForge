import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import Pager, { PaginatedResponse } from '@/components/common/Pager';
import { apiGet, apiUrl } from '@/services/api';
import { getStoredToken } from '@/services/token-store';

interface Artifact {
  id: string;
  type: string;
  version: number;
  name?: string;
  runId?: string;
  projectId?: string;
  format?: string;
  sizeBytes?: number | null;
  createdAt?: string;
  storagePath?: string;
}

function formatBytes(bytes?: number | null): string {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function typeVariant(type: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (type?.toLowerCase()) {
    case 'onnx':    return 'success';
    case 'pytorch': return 'warning';
    default:        return 'default';
  }
}

const PAGE_SIZE = 24;

async function downloadArtifact(modelId: string) {
  const token = getStoredToken();
  const res = await fetch(apiUrl(`/api/artifacts/models/${modelId}/download`), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Download failed: HTTP ${res.status}`);
  }
  const ctype = res.headers.get('content-type') || '';
  if (ctype.includes('application/json')) {
    // Presigned URL response → open in new tab so the browser can download.
    const data = await res.json();
    if (data.url) {
      window.location.href = data.url;
      return;
    }
  }
  // Stream → save via blob URL.
  const blob = await res.blob();
  const dispositionMatch = (res.headers.get('content-disposition') || '').match(
    /filename="?([^"]+)"?/,
  );
  const filename = dispositionMatch?.[1] || `model-${modelId}`;
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
}

export default function ArtifactsIndex() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [page, setPage]           = useState(1);
  const [total, setTotal]         = useState(0);
  const [downloadErr, setDownloadErr] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiGet<PaginatedResponse<Artifact>>(
      `/api/artifacts/models?page=${page}&page_size=${PAGE_SIZE}`,
    )
      .then((data) => {
        setArtifacts(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load artifacts'))
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <div className="py-6"><Loading label="Loading artifacts…" /></div>;
  if (error)   return <ErrorState title="Failed to load artifacts" description={error} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Artifacts</div>
          <h1>Model Artifacts</h1>
        </div>
        <Link to="/experiments" className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2">
          VIEW RUNS →
        </Link>
      </div>

      {downloadErr && (
        <div className="border border-[var(--hud-danger)] bg-[var(--hud-danger-dim)] px-3 py-2 text-xs font-mono text-[var(--hud-danger-text)]">
          {downloadErr}
        </div>
      )}

      {artifacts.length === 0 ? (
        <EmptyState
          title="No model artifacts"
          description="Train a model to generate artifacts for export and deployment."
        >
          <Link
            to="/experiments/new"
            className="inline-flex items-center h-7 px-3 text-xs font-mono border border-[var(--hud-accent)] text-[var(--hud-accent)] hover:bg-[var(--hud-accent-dim)] transition-colors"
          >
            New Training Run →
          </Link>
        </EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-px sm:grid-cols-2 lg:grid-cols-3 bg-[var(--hud-border-default)]">
            {artifacts.map((a) => (
              <div
                key={a.id}
                className="bg-[var(--hud-surface)] p-4 flex flex-col gap-2 hover:bg-[var(--hud-elevated)] transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="font-semibold text-sm text-[var(--hud-text-primary)] leading-tight">
                    {a.name || `Model v${a.version}`}
                  </div>
                  <Badge variant={typeVariant(a.type)}>{a.type}</Badge>
                </div>

                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs font-mono">
                  {a.runId && (
                    <div>
                      <span className="text-[var(--hud-text-muted)]">RUN </span>
                      <Link
                        to={`/experiments/runs/${a.runId}`}
                        className="text-[var(--hud-accent)] hover:underline underline-offset-1"
                      >
                        {a.runId.slice(0, 8)}…
                      </Link>
                    </div>
                  )}
                  <div>
                    <span className="text-[var(--hud-text-muted)]">SIZE </span>
                    <span className="text-[var(--hud-text-data)]">{formatBytes(a.sizeBytes)}</span>
                  </div>
                  {a.createdAt && (
                    <div className="col-span-2">
                      <span className="text-[var(--hud-text-muted)]">CREATED </span>
                      <span className="text-[var(--hud-text-secondary)]">
                        {new Date(a.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>

                <div className="mt-auto pt-2 border-t border-[var(--hud-border-subtle)] flex gap-2 flex-wrap">
                  <Link
                    to={`/artifacts/predict/${a.id}`}
                    className="text-[0.6875rem] font-mono text-[oklch(0.10_0.008_240)] bg-[var(--hud-accent)] border border-[var(--hud-accent)] px-2 py-0.5 hover:bg-[var(--hud-accent-hover)] transition-colors"
                  >
                    PREDICT
                  </Link>
                  <button
                    type="button"
                    onClick={() =>
                      downloadArtifact(a.id).catch((err) =>
                        setDownloadErr(err instanceof Error ? err.message : 'Download failed'),
                      )
                    }
                    className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:text-[var(--hud-accent)] hover:border-[var(--hud-accent)] transition-colors"
                  >
                    DOWNLOAD
                  </button>
                  <Link
                    to={`/evaluations/new?artifact_id=${a.id}`}
                    className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:text-[var(--hud-accent)] hover:border-[var(--hud-accent)] transition-colors"
                  >
                    EVALUATE
                  </Link>
                  <Link
                    to={`/artifacts/export/${a.id}`}
                    className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:text-[var(--hud-accent)] hover:border-[var(--hud-accent)] transition-colors"
                  >
                    EXPORT ONNX
                  </Link>
                  <Link
                    to={`/artifacts/lineage/${a.id}`}
                    className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:text-[var(--hud-accent)] hover:border-[var(--hud-accent)] transition-colors"
                  >
                    LINEAGE
                  </Link>
                </div>
              </div>
            ))}
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
