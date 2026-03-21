import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface Dataset {
  id: string;
  name: string;
  asset_count: number;
  latest_version?: number;
  latest_version_id?: string;
  project_id?: string;
  project_name?: string;
  created_at: string;
}

export default function DatasetsIndex() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') || '';

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = projectId ? `/api/datasets?project_id=${projectId}` : '/api/datasets';
    apiGet<Dataset[]>(url)
      .then(setDatasets)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load datasets'))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <div className="py-6"><Loading label="Loading datasets…" /></div>;
  if (error) return <ErrorState title="Failed to load datasets" description={error} />;

  const uploadTo = projectId ? `/datasets/upload?projectId=${projectId}` : '/datasets/upload';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">
            {projectId ? '// Projects / Datasets' : '// Datasets'}
          </div>
          <h1 className="flex items-center gap-2">
            Datasets
            {projectId && (
              <span className="text-xs font-mono text-[var(--hud-text-muted)]">
                (filtered)
                <Link to="/datasets" className="ml-2 text-[var(--hud-accent)] hover:underline">
                  CLEAR ×
                </Link>
              </span>
            )}
          </h1>
        </div>
        <Link
          to={uploadTo}
          className="inline-flex items-center h-8 px-3 text-xs font-mono font-medium border border-[var(--hud-accent)] bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] hover:bg-[var(--hud-accent-hover)] transition-colors tracking-wide"
        >
          + UPLOAD DATASET
        </Link>
      </div>

      {datasets.length === 0 ? (
        <EmptyState
          title="No datasets yet"
          description="Upload images or annotation files to create a dataset."
        >
          <Link
            to="/datasets/upload"
            className="inline-flex items-center h-7 px-3 text-xs font-mono border border-[var(--hud-accent)] text-[var(--hud-accent)] hover:bg-[var(--hud-accent-dim)] transition-colors"
          >
            Upload Dataset →
          </Link>
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-px sm:grid-cols-2 lg:grid-cols-3 bg-[var(--hud-border-default)]">
          {datasets.map((ds) => (
            <div key={ds.id} className="bg-[var(--hud-surface)] p-4 flex flex-col gap-2 hover:bg-[var(--hud-elevated)] transition-colors">
              {/* Title row */}
              <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-sm text-[var(--hud-text-primary)] leading-tight">
                  {ds.name}
                </div>
                {ds.latest_version != null && (
                  <Badge variant="default">v{ds.latest_version}</Badge>
                )}
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs font-mono">
                <div>
                  <span className="text-[var(--hud-text-muted)]">ASSETS </span>
                  <span className="text-[var(--hud-text-data)]">{ds.asset_count}</span>
                </div>
                {ds.project_name && (
                  <div className="truncate">
                    <span className="text-[var(--hud-text-muted)]">PROJ </span>
                    <span className="text-[var(--hud-text-secondary)]">{ds.project_name}</span>
                  </div>
                )}
                <div>
                  <span className="text-[var(--hud-text-muted)]">CREATED </span>
                  <span className="text-[var(--hud-text-secondary)]">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-auto pt-2 border-t border-[var(--hud-border-subtle)] flex flex-wrap gap-2">
                <Link
                  to={`/datasets/upload?datasetId=${ds.id}${ds.latest_version_id ? `&versionId=${ds.latest_version_id}` : ''}${ds.project_id ? `&projectId=${ds.project_id}` : ''}`}
                  className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:border-[var(--hud-accent)] transition-colors"
                >
                  UPLOAD
                </Link>
                <Link
                  to={`/datasets/version?datasetId=${ds.id}`}
                  className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:border-[var(--hud-accent)] transition-colors"
                >
                  SNAPSHOT
                </Link>
                {ds.asset_count > 0 && (
                  <Link
                    to={`/annotate/${ds.id}`}
                    className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:border-[var(--hud-accent)] transition-colors"
                  >
                    ANNOTATE
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
