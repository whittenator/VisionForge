import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface Artifact {
  id: string;
  type: string;
  version: number;
  name?: string;
  run_id?: string;
  project_id?: string;
  project_name?: string;
  file_size_bytes?: number;
  created_at: string;
}

function formatBytes(bytes: number): string {
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

export default function ArtifactsIndex() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);

  useEffect(() => {
    apiGet<Artifact[]>('/api/artifacts/models')
      .then(setArtifacts)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load artifacts'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="py-6"><Loading label="Loading artifacts…" /></div>;
  if (error)   return <ErrorState title="Failed to load artifacts" description={error} />;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Artifacts</div>
          <h1>Model Artifacts</h1>
        </div>
        <Link to="/experiments" className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2">
          VIEW RUNS →
        </Link>
      </div>

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
        <div className="grid grid-cols-1 gap-px sm:grid-cols-2 lg:grid-cols-3 bg-[var(--hud-border-default)]">
          {artifacts.map((a) => (
            <div key={a.id} className="bg-[var(--hud-surface)] p-4 flex flex-col gap-2 hover:bg-[var(--hud-elevated)] transition-colors">
              {/* Title + badge */}
              <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-sm text-[var(--hud-text-primary)] leading-tight">
                  {a.name || `Model v${a.version}`}
                </div>
                <Badge variant={typeVariant(a.type)}>{a.type}</Badge>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs font-mono">
                {a.project_name && (
                  <div className="col-span-2 truncate">
                    <span className="text-[var(--hud-text-muted)]">PROJ </span>
                    <span className="text-[var(--hud-text-secondary)]">{a.project_name}</span>
                  </div>
                )}
                {a.run_id && (
                  <div>
                    <span className="text-[var(--hud-text-muted)]">RUN </span>
                    <Link
                      to={`/experiments/runs/${a.run_id}`}
                      className="text-[var(--hud-accent)] hover:underline underline-offset-1"
                    >
                      {a.run_id.slice(0, 8)}…
                    </Link>
                  </div>
                )}
                {a.file_size_bytes != null && (
                  <div>
                    <span className="text-[var(--hud-text-muted)]">SIZE </span>
                    <span className="text-[var(--hud-text-data)]">{formatBytes(a.file_size_bytes)}</span>
                  </div>
                )}
                <div>
                  <span className="text-[var(--hud-text-muted)]">CREATED </span>
                  <span className="text-[var(--hud-text-secondary)]">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-auto pt-2 border-t border-[var(--hud-border-subtle)] flex gap-2">
                <Link
                  to={`/artifacts/export/${a.id}`}
                  className="text-[0.6875rem] font-mono text-[oklch(0.10_0.008_240)] bg-[var(--hud-accent)] border border-[var(--hud-accent)] px-2 py-0.5 hover:bg-[var(--hud-accent-hover)] transition-colors"
                >
                  EXPORT ONNX
                </Link>
                <Link
                  to={`/artifacts/export/${a.id}`}
                  className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:text-[var(--hud-accent)] hover:border-[var(--hud-accent)] transition-colors"
                >
                  LINEAGE
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
