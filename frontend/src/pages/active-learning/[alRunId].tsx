import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import { apiGet, apiPost } from '@/services/api';

interface ALItem {
  id: string;
  asset_id: string;
  priority: number;
  resolved_status: 'pending' | 'resolved';
}

interface ALProgress {
  al_run_id: string;
  total: number;
  resolved: number;
  pending: number;
  last_train_run_id: string | null;
}

interface RetrainResponse {
  al_run_id: string;
  train_run_id: string;
  job_id: string;
  status: string;
  resolved_count: number;
}

interface JobStatus {
  id: string;
  status: string;
  progress: number;
}

function statusVariant(s: string): 'default' | 'success' | 'warning' {
  if (s === 'resolved') return 'success';
  return 'default';
}

export default function ALRunDetail() {
  const { alRunId } = useParams<{ alRunId: string }>();
  const [items, setItems] = useState<ALItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ALProgress | null>(null);
  const [retraining, setRetraining] = useState(false);
  const [retrainError, setRetrainError] = useState<string | null>(null);
  const [trainRunId, setTrainRunId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);

  function reload() {
    if (!alRunId) return;
    apiGet<ALItem[]>(`/api/al/runs/${alRunId}/items`)
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load AL items'))
      .finally(() => setLoading(false));
    apiGet<ALProgress>(`/api/al/runs/${alRunId}/progress`)
      .then(setProgress)
      .catch(() => {});
  }

  useEffect(reload, [alRunId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll the spawned training job's progress until it reaches a terminal state.
  useEffect(() => {
    const jobId = job?.id;
    if (!jobId) return;
    if (job && ['succeeded', 'failed'].includes(job.status)) return;
    const timer = setInterval(() => {
      apiGet<JobStatus>(`/api/jobs/${jobId}`)
        .then(setJob)
        .catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  async function retrain() {
    if (!alRunId) return;
    setRetraining(true);
    setRetrainError(null);
    try {
      const res = await apiPost<RetrainResponse>(`/api/al/runs/${alRunId}/retrain`, {});
      setTrainRunId(res.train_run_id);
      setJob({ id: res.job_id, status: res.status, progress: 0 });
      reload();
    } catch (err) {
      setRetrainError(err instanceof Error ? err.message : 'Failed to start retrain');
    } finally {
      setRetraining(false);
    }
  }

  async function resolve(item: ALItem) {
    setResolvingId(item.id);
    try {
      await apiPost(`/api/al/runs/${alRunId}/items/${item.id}/resolve`, {});
      setItems((prev) =>
        prev.map((i) => (i.id === item.id ? { ...i, resolved_status: 'resolved' } : i)),
      );
    } catch (err) {
      console.error(err);
    } finally {
      setResolvingId(null);
    }
  }

  if (loading)
    return (
      <div className="py-6">
        <Loading label="Loading AL run items…" />
      </div>
    );
  if (error) return <ErrorState title="Failed to load AL run" description={error} />;

  const pending = items.filter((i) => i.resolved_status === 'pending');
  const resolved = items.filter((i) => i.resolved_status === 'resolved');
  const progressPct = items.length ? Math.round((resolved.length / items.length) * 100) : 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/active-learning" className="hover:text-[var(--hud-accent)] transition-colors">
            ACTIVE LEARNING
          </Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">{alRunId?.slice(0, 8)}…</span>
        </nav>
        <div className="flex items-center justify-between gap-4">
          <h1>AL Run Items</h1>
          <Link
            to="/active-learning/new"
            className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2"
          >
            + NEW RUN
          </Link>
        </div>
      </div>

      {/* Progress bar */}
      {items.length > 0 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[var(--hud-text-muted)]">Annotation Progress</span>
            <span className="text-[var(--hud-text-data)]">
              {resolved.length} / {items.length} resolved ({progressPct}%)
            </span>
          </div>
          <div className="h-1.5 w-full bg-[var(--hud-inset)] overflow-hidden">
            <div
              className="h-full bg-[var(--hud-accent)] transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Retrain feedback loop */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="label-overline">RETRAIN LOOP</div>
            <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-1">
              Launch a training run from the {resolved.length} resolved sample
              {resolved.length === 1 ? '' : 's'}.
            </p>
          </div>
          <Button
            size="sm"
            onClick={retrain}
            disabled={retraining || resolved.length === 0}
            title={resolved.length === 0 ? 'Resolve at least one item first' : undefined}
          >
            {retraining ? 'STARTING…' : 'RETRAIN FROM RESOLVED'}
          </Button>
        </div>

        {retrainError && (
          <div className="text-[0.6875rem] font-mono text-[var(--hud-danger)]">{retrainError}</div>
        )}

        {trainRunId && (
          <div className="border-t border-[var(--hud-border-subtle)] pt-2 flex items-center justify-between gap-3 text-xs font-mono">
            <Link
              to={`/experiments/runs/${trainRunId}`}
              className="text-[var(--hud-accent)] hover:underline underline-offset-2"
            >
              VIEW TRAINING RUN {trainRunId.slice(0, 8)}…
            </Link>
            {job && (
              <Badge variant={job.status === 'succeeded' ? 'success' : 'default'}>
                {job.status} {job.progress ? `· ${Math.round(job.progress * 100)}%` : ''}
              </Badge>
            )}
          </div>
        )}

        {progress?.last_train_run_id && progress.last_train_run_id !== trainRunId && (
          <div className="border-t border-[var(--hud-border-subtle)] pt-2 text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
            Last retrain:{' '}
            <Link
              to={`/experiments/runs/${progress.last_train_run_id}`}
              className="text-[var(--hud-accent)] hover:underline underline-offset-2"
            >
              {progress.last_train_run_id.slice(0, 8)}…
            </Link>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="border border-[var(--hud-border-default)] px-4 py-8 text-center text-xs font-mono text-[var(--hud-text-muted)]">
          No items in this AL run.
        </div>
      ) : (
        <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
          {/* Pending items first, then resolved */}
          {[...pending, ...resolved].map((item) => (
            <div
              key={item.id}
              className={[
                'flex items-center justify-between px-4 py-3 transition-colors',
                item.resolved_status === 'resolved'
                  ? 'opacity-60'
                  : 'hover:bg-[var(--hud-elevated)]',
              ].join(' ')}
            >
              <div className="flex items-center gap-3">
                <Badge variant={statusVariant(item.resolved_status)}>{item.resolved_status}</Badge>
                <div>
                  <code className="text-xs font-mono text-[var(--hud-text-secondary)]">
                    {item.asset_id}
                  </code>
                  <div className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-0.5">
                    priority {item.priority.toFixed(3)}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  to={`/annotate/${item.asset_id}`}
                  className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] border border-[var(--hud-border-default)] px-2 py-0.5 hover:border-[var(--hud-accent)] transition-colors"
                >
                  ANNOTATE
                </Link>
                {item.resolved_status === 'pending' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => resolve(item)}
                    disabled={resolvingId === item.id}
                  >
                    {resolvingId === item.id ? '…' : 'RESOLVE'}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
