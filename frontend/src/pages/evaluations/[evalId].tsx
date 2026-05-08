import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface PerClass {
  precision: number;
  recall: number;
  f1: number;
  support: number;
  ap50?: number;
}

interface FpFn {
  asset_id: string;
  predicted: string | null;
  ground_truth: string | null;
  score: number | null;
  kind: string;
}

interface Evaluation {
  id: string;
  artifact_id: string;
  dataset_version_id: string;
  status: string;
  metrics: Record<string, number> | null;
  per_class: Record<string, PerClass> | null;
  confusion: number[][] | null;
  classes: string[] | null;
  samples: FpFn[] | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

function pct(v: number | null | undefined) {
  if (v == null) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

function statusBadge(status: string) {
  if (status === 'succeeded') return <Badge variant="success">DONE</Badge>;
  if (status === 'running') return <Badge variant="info">RUNNING</Badge>;
  if (status === 'failed') return <Badge variant="danger">FAILED</Badge>;
  return <Badge variant="default">{status.toUpperCase()}</Badge>;
}

export default function EvaluationDetail() {
  const { evalId } = useParams();
  const [data, setData] = useState<Evaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!evalId) return;
    let cancelled = false;
    function load() {
      apiGet<Evaluation>(`/api/evaluations/${evalId}`)
        .then((d) => {
          if (!cancelled) setData(d);
        })
        .catch((err) => {
          if (!cancelled)
            setError(err instanceof Error ? err.message : 'Failed to load');
        });
    }
    load();
    const t = setInterval(() => {
      if (data && data.status !== 'queued' && data.status !== 'running') return;
      load();
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evalId]);

  if (error) return <ErrorState description={error} />;
  if (!data)
    return (
      <div className="flex items-center gap-2 text-xs font-mono text-[var(--hud-text-muted)]">
        <Spinner size={14} /> Loading…
      </div>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Evaluations / Detail</div>
          <h1>Evaluation {data.id.slice(0, 8)}</h1>
          <div className="text-xs font-mono text-[var(--hud-text-muted)] flex items-center gap-2 mt-1">
            {statusBadge(data.status)}
            <span>
              ARTIFACT{' '}
              <Link
                to={`/artifacts`}
                className="text-[var(--hud-accent)] hover:underline"
              >
                {data.artifact_id.slice(0, 8)}
              </Link>
            </span>
            <span>·</span>
            <span>
              DATASET VERSION{' '}
              <span style={{ color: 'var(--hud-text-data)' }}>
                {data.dataset_version_id.slice(0, 8)}
              </span>
            </span>
          </div>
        </div>
      </div>

      {data.error_message && (
        <ErrorState title="Evaluation failed" description={data.error_message} />
      )}

      {/* Top metrics */}
      {data.metrics && (
        <div className="grid grid-cols-4 gap-px bg-[var(--hud-border-default)]">
          {Object.entries(data.metrics).map(([k, v]) => (
            <div key={k} className="bg-[var(--hud-surface)] p-3">
              <div className="label-overline">{k}</div>
              <div className="text-2xl font-semibold font-mono text-[var(--hud-text-data)]">
                {typeof v === 'number'
                  ? k === 'samples' || k === 'count'
                    ? v
                    : pct(v)
                  : String(v)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Per-class table */}
      {data.per_class && Object.keys(data.per_class).length > 0 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="label-overline px-3 py-2 border-b border-[var(--hud-border-subtle)]">
            Per-class metrics
          </div>
          <table className="w-full text-xs font-mono">
            <thead className="bg-[var(--hud-inset)] text-[var(--hud-text-muted)]">
              <tr className="text-left">
                <th className="p-2">CLASS</th>
                <th className="p-2">P</th>
                <th className="p-2">R</th>
                <th className="p-2">F1</th>
                <th className="p-2">AP@50</th>
                <th className="p-2">SUPPORT</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.per_class).map(([cls, pc]) => (
                <tr
                  key={cls}
                  className="border-t border-[var(--hud-border-subtle)] hover:bg-[var(--hud-elevated)]"
                >
                  <td className="p-2 text-[var(--hud-text-data)]">{cls}</td>
                  <td className="p-2">{pct(pc.precision)}</td>
                  <td className="p-2">{pct(pc.recall)}</td>
                  <td className="p-2">{pct(pc.f1)}</td>
                  <td className="p-2">{pc.ap50 != null ? pct(pc.ap50) : '—'}</td>
                  <td className="p-2 text-[var(--hud-text-muted)]">{pc.support}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Confusion matrix */}
      {data.confusion && data.classes && data.confusion.length > 0 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="label-overline px-3 py-2 border-b border-[var(--hud-border-subtle)]">
            Confusion matrix (rows = ground truth, cols = predicted)
          </div>
          <div className="overflow-auto p-3">
            <table className="text-[0.6875rem] font-mono">
              <thead>
                <tr>
                  <th className="p-1"></th>
                  {data.classes.map((c) => (
                    <th
                      key={c}
                      className="p-1 text-[var(--hud-text-muted)] text-center"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.confusion.map((row, i) => {
                  const max = Math.max(...row, 1);
                  return (
                    <tr key={i}>
                      <th className="p-1 text-[var(--hud-text-muted)] text-right">
                        {data.classes![i]}
                      </th>
                      {row.map((v, j) => {
                        const intensity = v / max;
                        const bg = `oklch(${0.18 + intensity * 0.4} 0.10 ${
                          i === j ? 155 : 20
                        })`;
                        return (
                          <td
                            key={j}
                            className="border border-[var(--hud-border-subtle)] text-center"
                            style={{
                              background: v > 0 ? bg : 'transparent',
                              color:
                                v > 0
                                  ? 'var(--hud-text-data)'
                                  : 'var(--hud-text-muted)',
                              minWidth: '36px',
                              padding: '4px 8px',
                            }}
                          >
                            {v}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* FP / FN samples */}
      {data.samples && data.samples.length > 0 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="label-overline px-3 py-2 border-b border-[var(--hud-border-subtle)]">
            False positives / false negatives ({data.samples.length})
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-px bg-[var(--hud-border-subtle)]">
            {data.samples.map((s, i) => (
              <Link
                key={i}
                to={`/annotate/${s.asset_id}`}
                className="bg-[var(--hud-surface)] hover:bg-[var(--hud-elevated)] p-3"
              >
                <div className="flex items-center justify-between">
                  <Badge variant={s.kind === 'fp' ? 'danger' : 'warning'}>
                    {s.kind.toUpperCase()}
                  </Badge>
                  {s.score != null && (
                    <span className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
                      {pct(s.score)}
                    </span>
                  )}
                </div>
                <div className="mt-2 text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
                  ASSET {s.asset_id.slice(0, 8)}
                </div>
                <div className="mt-1 text-xs font-mono text-[var(--hud-text-data)]">
                  {s.predicted ? `pred: ${s.predicted}` : 'no prediction'}
                </div>
                <div className="text-xs font-mono text-[var(--hud-text-muted)]">
                  {s.ground_truth ? `gt: ${s.ground_truth}` : 'no ground truth'}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
