import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface ArtifactLite {
  id: string;
  name?: string;
  version?: number;
  type?: string;
  format?: string;
  sizeBytes?: number | null;
  storagePath?: string | null;
  createdAt?: string | null;
  runId?: string | null;
}

interface Lineage {
  artifact: ArtifactLite;
  experiment_run: {
    id: string;
    name: string;
    status: string;
    params?: Record<string, unknown>;
    metrics?: Record<string, unknown> | unknown[];
    started_at?: string | null;
    completed_at?: string | null;
  } | null;
  dataset_version: {
    id: string;
    version: number;
    asset_count: number;
    locked: boolean;
  } | null;
  dataset: {
    id: string;
    name: string;
    task_type?: string | null;
  } | null;
  classes: string[];
  cluster: {
    id: string;
    name: string;
    kind: string;
    gpu_vendor: string;
  } | null;
  siblings: ArtifactLite[];
  evaluations: Array<{
    id: string;
    status: string;
    dataset_version_id: string;
    primary_metric_name: string | null;
    primary_metric: number | null;
    created_at: string | null;
    completed_at: string | null;
  }>;
}

function evalStatusBadge(status: string) {
  switch (status) {
    case 'succeeded': return <Badge variant="success">DONE</Badge>;
    case 'running':   return <Badge variant="warning">RUNNING</Badge>;
    case 'failed':    return <Badge variant="danger">FAILED</Badge>;
    default:          return <Badge>{status.toUpperCase()}</Badge>;
  }
}

function formatBytes(bytes?: number | null) {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export default function ArtifactsLineage() {
  const { modelId } = useParams<{ modelId: string }>();
  const [data, setData] = useState<Lineage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!modelId) return;
    setLoading(true);
    apiGet<Lineage>(`/api/artifacts/models/${modelId}/lineage`)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load lineage'))
      .finally(() => setLoading(false));
  }, [modelId]);

  if (loading) return <div className="py-6"><Loading label="Loading lineage…" /></div>;
  if (error) return <ErrorState title="Lineage unavailable" description={error} />;
  if (!data) return <ErrorState title="Not found" />;

  const a = data.artifact;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Artifacts / Lineage</div>
          <h1 className="flex items-center gap-2">
            {a.name || `Model v${a.version}`}
            {a.type && <Badge variant="default">{a.type}</Badge>}
            {a.format && <Badge variant="default">{a.format}</Badge>}
          </h1>
          <p className="text-xs text-[var(--hud-text-muted)] mt-1">
            Provenance for this model: training run → dataset version → class map → evaluations.
          </p>
        </div>
        <Link
          to="/artifacts"
          className="text-xs font-mono text-[var(--hud-accent)] hover:underline"
        >
          ← ARTIFACTS
        </Link>
      </div>

      <div className="grid gap-px md:grid-cols-2 bg-[var(--hud-border-default)]">
        <Section label="Artifact">
          <Row k="ID" v={a.id} mono />
          <Row k="Version" v={`v${a.version ?? '—'}`} />
          <Row k="Size" v={formatBytes(a.sizeBytes)} />
          <Row k="Storage" v={a.storagePath || '—'} mono />
          <Row k="Created" v={a.createdAt ? new Date(a.createdAt).toLocaleString() : '—'} />
        </Section>

        <Section label="Training Run">
          {data.experiment_run ? (
            <>
              <Row
                k="Run"
                v={
                  <Link
                    to={`/experiments/runs/${data.experiment_run.id}`}
                    className="text-[var(--hud-accent)] hover:underline"
                  >
                    {data.experiment_run.name || data.experiment_run.id.slice(0, 12)}
                  </Link>
                }
              />
              <Row k="Status" v={data.experiment_run.status} />
              <Row
                k="Started"
                v={
                  data.experiment_run.started_at
                    ? new Date(data.experiment_run.started_at).toLocaleString()
                    : '—'
                }
              />
              <Row
                k="Completed"
                v={
                  data.experiment_run.completed_at
                    ? new Date(data.experiment_run.completed_at).toLocaleString()
                    : '—'
                }
              />
              <Row
                k="Params"
                v={
                  <code className="text-[0.6875rem] text-[var(--hud-text-data)] break-all">
                    {Object.entries(data.experiment_run.params || {})
                      .slice(0, 6)
                      .map(([k, v]) => `${k}=${String(v)}`)
                      .join(' ') || '—'}
                  </code>
                }
              />
            </>
          ) : (
            <div className="text-xs font-mono text-[var(--hud-text-muted)]">No run linked.</div>
          )}
        </Section>

        <Section label="Dataset / Version">
          {data.dataset && data.dataset_version ? (
            <>
              <Row
                k="Dataset"
                v={
                  <Link
                    to={`/datasets/${data.dataset.id}`}
                    className="text-[var(--hud-accent)] hover:underline"
                  >
                    {data.dataset.name}
                  </Link>
                }
              />
              <Row k="Task" v={data.dataset.task_type || '—'} />
              <Row k="Version" v={`v${data.dataset_version.version}`} />
              <Row k="Assets" v={String(data.dataset_version.asset_count)} mono />
              <Row k="Locked" v={data.dataset_version.locked ? 'YES' : 'NO'} />
            </>
          ) : (
            <div className="text-xs font-mono text-[var(--hud-text-muted)]">No dataset linked.</div>
          )}
        </Section>

        <Section label="Compute Cluster">
          {data.cluster ? (
            <>
              <Row k="Cluster" v={data.cluster.name} />
              <Row k="Kind" v={data.cluster.kind.toUpperCase()} />
              <Row k="GPU" v={data.cluster.gpu_vendor.toUpperCase()} />
            </>
          ) : (
            <div className="text-xs font-mono text-[var(--hud-text-muted)]">
              No cluster recorded (run executed on shared queue).
            </div>
          )}
        </Section>
      </div>

      <Section label={`Classes (${data.classes.length})`}>
        {data.classes.length === 0 ? (
          <div className="text-xs font-mono text-[var(--hud-text-muted)]">No class map.</div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {data.classes.map((c) => (
              <span
                key={c}
                className="text-[0.6875rem] font-mono text-[var(--hud-text-data)] border border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-2 py-0.5"
              >
                {c}
              </span>
            ))}
          </div>
        )}
      </Section>

      <Section label={`Sibling Artifacts (${data.siblings.length})`}>
        {data.siblings.length === 0 ? (
          <div className="text-xs font-mono text-[var(--hud-text-muted)]">
            No other artifacts produced by the same run.
          </div>
        ) : (
          <ul className="divide-y divide-[var(--hud-border-subtle)]">
            {data.siblings.map((s) => (
              <li key={s.id} className="flex items-center justify-between py-1.5 text-xs font-mono">
                <span className="text-[var(--hud-text-muted)]">
                  {s.type} v{s.version}
                </span>
                <Link
                  to={`/artifacts/lineage/${s.id}`}
                  className="text-[var(--hud-accent)] hover:underline"
                >
                  VIEW LINEAGE →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section label={`Evaluations (${data.evaluations.length})`}>
        {data.evaluations.length === 0 ? (
          <div className="text-xs font-mono text-[var(--hud-text-muted)]">
            This artifact has not been evaluated yet.
          </div>
        ) : (
          <ul className="divide-y divide-[var(--hud-border-subtle)]">
            {data.evaluations.map((ev) => (
              <li key={ev.id} className="flex items-center justify-between py-1.5 text-xs font-mono">
                <span className="text-[var(--hud-text-muted)]">
                  {ev.created_at ? new Date(ev.created_at).toLocaleString() : '—'}
                </span>
                <span className="flex items-center gap-3">
                  {evalStatusBadge(ev.status)}
                  {ev.primary_metric != null && ev.primary_metric_name && (
                    <span className="text-[var(--hud-text-data)]">
                      {ev.primary_metric_name} {(ev.primary_metric * 100).toFixed(1)}%
                    </span>
                  )}
                  <Link
                    to={`/evaluations/${ev.id}`}
                    className="text-[var(--hud-accent)] hover:underline"
                  >
                    VIEW →
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--hud-surface)]">
      <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
        <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
        <span className="label-overline">{label}</span>
      </div>
      <div className="px-4 py-3 text-xs font-mono space-y-1">{children}</div>
    </div>
  );
}

function Row({ k, v, mono = false }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="text-[var(--hud-text-muted)] tracking-widest uppercase min-w-[120px]">
        {k}
      </span>
      <span
        className={
          mono
            ? 'text-[var(--hud-text-data)] truncate'
            : 'text-[var(--hud-text-primary)]'
        }
      >
        {v}
      </span>
    </div>
  );
}
