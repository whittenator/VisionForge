import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface EvaluationSummary {
  id: string;
  artifact_id: string;
  dataset_version_id: string;
  status: string;
  primary_metric_name: string | null;
  primary_metric: number | null;
  created_at: string | null;
  completed_at: string | null;
}

function statusBadge(status: string) {
  if (status === 'succeeded') return <Badge variant="success">DONE</Badge>;
  if (status === 'running') return <Badge variant="info">RUNNING</Badge>;
  if (status === 'failed') return <Badge variant="danger">FAILED</Badge>;
  return <Badge variant="default">{status.toUpperCase()}</Badge>;
}

export default function EvaluationsIndex() {
  const [params] = useSearchParams();
  const [rows, setRows] = useState<EvaluationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const qp = new URLSearchParams();
    const artifact = params.get('artifact_id');
    if (artifact) qp.set('artifact_id', artifact);
    const dsv = params.get('dataset_version_id');
    if (dsv) qp.set('dataset_version_id', dsv);
    const project = params.get('project_id');
    if (project) qp.set('project_id', project);

    apiGet<EvaluationSummary[]>(`/api/evaluations?${qp.toString()}`)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'));
  }, [params]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Evaluations</div>
          <h1>Evaluations</h1>
          <p className="text-xs text-[var(--hud-text-muted)] mt-1">
            Run a model against a labeled dataset version. Get mAP / accuracy / per-class P/R/F1
            and an FP/FN viewer.
          </p>
        </div>
        <Link
          to="/evaluations/new"
          className="inline-flex items-center h-8 px-3 text-xs font-mono font-medium bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border border-[var(--hud-accent)]"
        >
          + NEW EVAL
        </Link>
      </div>

      {error && <ErrorState description={error} />}

      {rows === null && !error && (
        <div className="flex items-center gap-2 text-xs font-mono text-[var(--hud-text-muted)]">
          <Spinner size={14} /> Loading…
        </div>
      )}

      {rows && rows.length === 0 && (
        <EmptyState
          title="No evaluations yet"
          description="Click + NEW EVAL to score a trained model on a labeled dataset version."
        />
      )}

      {rows && rows.length > 0 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <table className="w-full text-xs font-mono">
            <thead className="bg-[var(--hud-inset)]">
              <tr className="text-left">
                <th className="p-2 label-overline">ID</th>
                <th className="p-2 label-overline">Status</th>
                <th className="p-2 label-overline">Metric</th>
                <th className="p-2 label-overline">Created</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-[var(--hud-border-subtle)] hover:bg-[var(--hud-elevated)]"
                >
                  <td className="p-2 text-[var(--hud-text-muted)]">{r.id.slice(0, 8)}</td>
                  <td className="p-2">{statusBadge(r.status)}</td>
                  <td className="p-2">
                    {r.primary_metric != null && r.primary_metric_name ? (
                      <span className="text-[var(--hud-text-data)]">
                        {r.primary_metric_name} {(r.primary_metric * 100).toFixed(1)}%
                      </span>
                    ) : (
                      <span className="text-[var(--hud-text-muted)]">—</span>
                    )}
                  </td>
                  <td className="p-2 text-[var(--hud-text-muted)]">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                  </td>
                  <td className="p-2 text-right">
                    <Link
                      to={`/evaluations/${r.id}`}
                      className="text-[var(--hud-accent)] hover:underline"
                    >
                      VIEW →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
