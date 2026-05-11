import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import Pager, { PaginatedResponse } from '@/components/common/Pager';
import { apiGet } from '@/services/api';

interface ALRun {
  id: string;
  project_id: string;
  strategy: string;
  created_at?: string;
}

const PAGE_SIZE = 25;

export default function ActiveLearningIndex() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') || '';
  const [runs, setRuns] = useState<ALRun[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (projectId) params.set('project_id', projectId);
    apiGet<PaginatedResponse<ALRun>>(`/api/al/runs?${params.toString()}`)
      .then((data) => {
        setRuns(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load AL runs'))
      .finally(() => setLoading(false));
  }, [projectId, page]);

  if (loading) return <div className="py-6"><Loading label="Loading active learning runs…" /></div>;
  if (error) return <ErrorState title="Failed to load active learning runs" description={error} />;

  const newRunTo = projectId ? `/active-learning/new?projectId=${projectId}` : '/active-learning/new';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Active Learning</div>
          <h1>Active Learning Runs</h1>
        </div>
        <Link
          to={newRunTo}
          className="inline-flex items-center h-8 px-3 text-xs font-mono font-medium border border-[var(--hud-accent)] bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] hover:bg-[var(--hud-accent-hover)] transition-colors tracking-wide"
        >
          + NEW RUN
        </Link>
      </div>

      {runs.length === 0 ? (
        <EmptyState
          title="No active learning runs"
          description="Run active learning to automatically select the most informative unlabeled samples for annotation."
        >
          <Link
            to={newRunTo}
            className="inline-flex items-center h-7 px-3 text-xs font-mono border border-[var(--hud-accent)] text-[var(--hud-accent)] hover:bg-[var(--hud-accent-dim)] transition-colors"
          >
            Start AL Run →
          </Link>
        </EmptyState>
      ) : (
        <>
          <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
            {runs.map((r) => (
              <Link
                key={r.id}
                to={`/active-learning/${r.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-[var(--hud-elevated)] transition-colors group"
              >
                <div>
                  <div className="text-sm font-mono font-semibold text-[var(--hud-text-primary)]">
                    {r.id.slice(0, 8)}…
                  </div>
                  {r.created_at && (
                    <div className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-0.5">
                      {new Date(r.created_at).toLocaleString()}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant="default">{r.strategy}</Badge>
                  <span className="text-xs font-mono text-[var(--hud-accent)] group-hover:underline">
                    VIEW →
                  </span>
                </div>
              </Link>
            ))}
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
