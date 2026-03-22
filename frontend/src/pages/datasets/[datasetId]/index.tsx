import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import { apiGet, apiPost } from '@/services/api';

interface DatasetVersion {
  id: string;
  version: number;
  asset_count: number;
  locked: boolean;
  notes?: string;
  created_at?: string;
}

interface DatasetDetail {
  id: string;
  name: string;
  description?: string;
  project_id?: string;
  classes: Array<string | { name: string; color?: string }>;
  versions: DatasetVersion[];
  created_at?: string;
}

export default function DatasetDetail() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotMsg, setSnapshotMsg] = useState<string | null>(null);

  function reload() {
    if (!datasetId) return;
    setLoading(true);
    apiGet<DatasetDetail>(`/api/datasets/${datasetId}`)
      .then(setDataset)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load dataset'))
      .finally(() => setLoading(false));
  }

  useEffect(reload, [datasetId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function createSnapshot() {
    if (!datasetId) return;
    setSnapshotLoading(true);
    setSnapshotMsg(null);
    try {
      const v = await apiPost<DatasetVersion>(`/api/datasets/${datasetId}/snapshot`, {});
      setSnapshotMsg(`Snapshot v${v.version} created (${v.asset_count} assets)`);
      reload();
    } catch (err) {
      setSnapshotMsg(err instanceof Error ? err.message : 'Failed to create snapshot');
    } finally {
      setSnapshotLoading(false);
    }
  }

  if (loading) return <div className="py-6"><Loading label="Loading dataset…" /></div>;
  if (error) return <ErrorState title="Failed to load dataset" description={error} />;
  if (!dataset) return <ErrorState title="Dataset not found" />;

  const latestVersion = dataset.versions[0];
  const classNames = dataset.classes.map((c) =>
    typeof c === 'string' ? c : c.name
  );

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/datasets" className="hover:text-[var(--hud-accent)] transition-colors">DATASETS</Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">{dataset.name.toUpperCase()}</span>
        </nav>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="flex items-center gap-2">
              {dataset.name}
              {latestVersion && (
                <Badge variant="default">v{latestVersion.version}</Badge>
              )}
            </h1>
            {dataset.description && (
              <p className="text-xs text-[var(--hud-text-muted)] mt-1 max-w-xl">{dataset.description}</p>
            )}
          </div>
          <div className="flex gap-2 flex-shrink-0 flex-wrap">
            {latestVersion && (
              <>
                <Link
                  to={`/datasets/upload?datasetId=${dataset.id}&versionId=${latestVersion.id}${dataset.project_id ? `&projectId=${dataset.project_id}` : ''}`}
                  className="inline-flex items-center h-8 px-3 text-xs font-mono font-medium border border-[var(--hud-accent)] bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] hover:bg-[var(--hud-accent-hover)] transition-colors tracking-wide"
                >
                  + UPLOAD
                </Link>
                {latestVersion.asset_count > 0 && (
                  <Link
                    to={`/datasets/${dataset.id}/annotate`}
                    className="inline-flex items-center h-8 px-3 text-xs font-mono border border-[var(--hud-border-strong)] text-[var(--hud-text-secondary)] hover:border-[var(--hud-accent)] hover:text-[var(--hud-accent)] transition-colors tracking-wide"
                  >
                    ANNOTATE
                  </Link>
                )}
              </>
            )}
            <Button size="sm" variant="outline" onClick={createSnapshot} disabled={snapshotLoading}>
              {snapshotLoading ? 'Creating…' : 'SNAPSHOT'}
            </Button>
          </div>
        </div>
        {snapshotMsg && (
          <p className="mt-2 text-xs font-mono text-[var(--hud-success-text)]">{snapshotMsg}</p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        {/* Version History */}
        <section>
          <div className="label-overline mb-2">Version History</div>
          {dataset.versions.length === 0 ? (
            <div className="border border-[var(--hud-border-default)] px-4 py-6 text-center text-xs font-mono text-[var(--hud-text-muted)]">
              No versions yet. Upload assets and create a snapshot.
            </div>
          ) : (
            <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
              {dataset.versions.map((v, idx) => (
                <div key={v.id} className="flex items-center justify-between px-4 py-3 hover:bg-[var(--hud-elevated)] transition-colors">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-semibold text-[var(--hud-text-primary)]">
                        v{v.version}
                      </span>
                      {idx === 0 && (
                        <Badge variant="success">LATEST</Badge>
                      )}
                      {v.locked && (
                        <Badge variant="default">LOCKED</Badge>
                      )}
                    </div>
                    {v.notes && (
                      <p className="text-xs text-[var(--hud-text-muted)] mt-0.5 max-w-xs truncate">{v.notes}</p>
                    )}
                    {v.created_at && (
                      <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-0.5">
                        {new Date(v.created_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <span className="text-[var(--hud-text-muted)]">
                      <span className="text-[var(--hud-text-data)]">{v.asset_count}</span> assets
                    </span>
                    {v.asset_count > 0 && (
                      <Link
                        to={`/datasets/upload?datasetId=${dataset.id}&versionId=${v.id}${dataset.project_id ? `&projectId=${dataset.project_id}` : ''}`}
                        className="text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] transition-colors"
                      >
                        UPLOAD
                      </Link>
                    )}
                    {v.asset_count > 0 && (
                      <Link
                        to={`/datasets/${dataset.id}/annotate`}
                        className="text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] transition-colors"
                      >
                        ANNOTATE
                      </Link>
                    )}
                    <Link
                      to={`/experiments/new?datasetVersionId=${v.id}${dataset.project_id ? `&projectId=${dataset.project_id}` : ''}`}
                      className="text-[var(--hud-accent)] hover:underline underline-offset-2"
                    >
                      TRAIN →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Classes + Info */}
        <div className="space-y-4">
          {/* Class Map */}
          <section>
            <div className="label-overline mb-2">Class Map</div>
            <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-4">
              {classNames.length === 0 ? (
                <p className="text-xs font-mono text-[var(--hud-text-muted)]">
                  No classes defined. Add via the annotator or dataset API.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {classNames.map((cls, i) => (
                    <span
                      key={i}
                      className="text-[0.6875rem] font-mono px-2 py-0.5 border border-[var(--hud-border-default)] text-[var(--hud-text-secondary)]"
                    >
                      {cls}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Dataset Metadata */}
          <section>
            <div className="label-overline mb-2">Details</div>
            <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] divide-y divide-[var(--hud-border-subtle)]">
              {[
                { label: 'ID', value: <code className="text-[0.6875rem]">{dataset.id}</code> },
                { label: 'Versions', value: dataset.versions.length },
                { label: 'Total Assets', value: latestVersion?.asset_count ?? 0 },
                ...(dataset.created_at ? [{ label: 'Created', value: new Date(dataset.created_at).toLocaleDateString() }] : []),
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between px-4 py-2 text-xs font-mono">
                  <span className="text-[var(--hud-text-muted)] uppercase tracking-wide">{label}</span>
                  <span className="text-[var(--hud-text-data)]">{value}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Quick Actions */}
          <section>
            <div className="label-overline mb-2">Quick Actions</div>
            <div className="flex flex-col gap-1">
              {dataset.project_id && (
                <Link
                  to={`/experiments/new?projectId=${dataset.project_id}${latestVersion ? `&datasetVersionId=${latestVersion.id}` : ''}`}
                  className="text-xs font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] border border-[var(--hud-border-default)] px-3 py-2 hover:border-[var(--hud-accent)] transition-colors text-center"
                >
                  Launch Training Run →
                </Link>
              )}
              <Link
                to={`/datasets/version?datasetId=${dataset.id}`}
                className="text-xs font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] border border-[var(--hud-border-default)] px-3 py-2 hover:border-[var(--hud-accent)] transition-colors text-center"
              >
                Create Snapshot →
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
