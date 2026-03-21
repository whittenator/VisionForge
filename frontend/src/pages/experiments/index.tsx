import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import { apiGet } from '@/services/api';

interface Run {
  id: string;
  name?: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  createdAt: string;
}

function statusVariant(s: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (s) {
    case 'succeeded': return 'success';
    case 'running':   return 'warning';
    case 'failed':    return 'danger';
    default:          return 'default';
  }
}

export default function ExperimentsIndex() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Run[]>('/api/experiments/runs')
      .then(setRuns)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Experiments</div>
          <h1>Training Runs</h1>
        </div>
        <Button as-child>
          <Link to="/experiments/new">+ New Run</Link>
        </Button>
      </div>

      {loading ? (
        <div className="py-6"><Loading label="Loading runs…" /></div>
      ) : runs.length === 0 ? (
        <EmptyState
          title="No training runs"
          description="Launch a new training run to train your first model."
        >
          <Link
            to="/experiments/new"
            className="inline-flex items-center h-7 px-3 text-xs font-mono border border-[var(--hud-accent)] text-[var(--hud-accent)] hover:bg-[var(--hud-accent-dim)] transition-colors"
          >
            New Training Run →
          </Link>
        </EmptyState>
      ) : (
        <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2 bg-[var(--hud-inset)]">
            <span className="label-overline">Run</span>
            <span className="label-overline">Status</span>
            <span className="label-overline">Started</span>
            <span className="label-overline">Details</span>
          </div>

          {runs.map((r) => (
            <div
              key={r.id}
              className="grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center px-4 py-2.5 hover:bg-[var(--hud-elevated)] transition-colors"
            >
              <div>
                <div className="text-sm font-medium text-[var(--hud-text-primary)]">
                  {r.name || `Run ${r.id.slice(0, 8)}`}
                </div>
                <div className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-0.5">
                  {r.id.slice(0, 16)}…
                </div>
              </div>
              <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
              <span className="text-xs font-mono text-[var(--hud-text-muted)] whitespace-nowrap">
                {r.createdAt ? new Date(r.createdAt).toLocaleDateString() : '—'}
              </span>
              <Link
                to={`/experiments/runs/${r.id}`}
                className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2 whitespace-nowrap"
              >
                VIEW →
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
