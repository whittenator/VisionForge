import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import { apiGet, apiPost } from '@/services/api';

interface Run {
  id: string;
  name: string;
  status: string;
  params_json?: string;
  metrics_json?: string;
  artifacts?: string;
  dataset_version_id?: string;
  created_at: string;
  completed_at?: string;
  project_id?: string;
}

type MetricPoint = Record<string, number | undefined> & { epoch: number };

interface PlotRecord {
  name: string;
  file: string;
  key: string;
  url?: string | null;
}

interface SplitInfo {
  counts: { train: number; val: number; test: number; unassigned?: number };
  ratios?: { train: number; val: number; test: number };
  seed?: number;
}

interface MetricsResponse {
  status: string;
  metrics: MetricPoint[];
  summary?: Record<string, number> | null;
  plots?: PlotRecord[];
  split?: SplitInfo | null;
}

const COLORS = [
  'oklch(0.72 0.10 82)',
  'oklch(0.60 0.10 155)',
  'oklch(0.68 0.16 20)',
  'oklch(0.72 0.08 230)',
  'oklch(0.70 0.10 75)',
  'oklch(0.66 0.14 300)',
];

// Chart panels: each groups same-unit series so a shared y-scale is meaningful.
const PANELS: { title: string; keys: string[] }[] = [
  {
    title: 'Loss (train vs val)',
    keys: [
      'train_box_loss',
      'val_box_loss',
      'train_cls_loss',
      'val_cls_loss',
      'train_dfl_loss',
      'val_dfl_loss',
      'loss',
    ],
  },
  { title: 'mAP', keys: ['mAP50', 'mAP50_95'] },
  { title: 'Precision / Recall', keys: ['precision', 'recall'] },
  { title: 'Accuracy', keys: ['top1', 'top5'] },
  { title: 'Learning Rate', keys: ['lr'] },
];

const SPLIT_COLORS: Record<string, string> = {
  train: 'oklch(0.60 0.10 155)',
  val: 'oklch(0.72 0.10 82)',
  test: 'oklch(0.72 0.08 230)',
};

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'succeeded':
      return 'success';
    case 'running':
      return 'warning';
    case 'failed':
      return 'danger';
    default:
      return 'default';
  }
}

function LineChart({ data, keys }: { data: MetricPoint[]; keys: string[] }) {
  const present = keys.filter((k) => data.some((d) => d[k] != null));
  if (!present.length) {
    return <p className="text-xs font-mono text-[var(--hud-text-muted)] py-4">No data.</p>;
  }
  const W = 460;
  const H = 160;
  const PAD = 34;
  const all = present.flatMap((k) => data.map((d) => d[k]).filter((v): v is number => v != null));
  const min = Math.min(...all);
  const max = Math.max(...all);
  const norm = (v: number) => (max === min ? 0.5 : (v - min) / (max - min));

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ background: 'var(--hud-inset)' }}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <line
            key={t}
            x1={PAD}
            y1={PAD + (1 - t) * (H - PAD * 2)}
            x2={W - PAD}
            y2={PAD + (1 - t) * (H - PAD * 2)}
            stroke="var(--hud-border-subtle)"
            strokeWidth="1"
          />
        ))}
        {/* y-axis min/max labels */}
        <text x={4} y={PAD + 4} fontSize="8" fill="var(--hud-text-muted)" fontFamily="monospace">
          {max.toFixed(3)}
        </text>
        <text x={4} y={H - PAD} fontSize="8" fill="var(--hud-text-muted)" fontFamily="monospace">
          {min.toFixed(3)}
        </text>
        {present.map((key, ki) => {
          const pts = data
            .map((d, i) => {
              const val = d[key];
              if (val == null) return null;
              const x = PAD + (i / Math.max(data.length - 1, 1)) * (W - PAD * 2);
              const y = PAD + (1 - norm(val)) * (H - PAD * 2);
              return `${x},${y}`;
            })
            .filter(Boolean)
            .join(' ');
          return (
            <polyline
              key={key}
              points={pts}
              fill="none"
              stroke={COLORS[ki % COLORS.length]}
              strokeWidth="1.5"
            />
          );
        })}
        <text
          x={W / 2}
          y={H - 4}
          textAnchor="middle"
          fontSize="9"
          fill="var(--hud-text-muted)"
          fontFamily="monospace"
        >
          EPOCH
        </text>
      </svg>
      <div className="flex flex-wrap gap-3 mt-2">
        {present.map((key, ki) => (
          <div key={key} className="flex items-center gap-1.5 text-xs font-mono">
            <div className="w-4 h-0.5" style={{ backgroundColor: COLORS[ki % COLORS.length] }} />
            <span className="text-[var(--hud-text-muted)]">{key}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
      <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
        <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
        <span className="label-overline">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function fmtMetric(key: string, v: number): string {
  if (/loss|lr/i.test(key)) return v.toFixed(4);
  return v < 1 ? `${(v * 100).toFixed(1)}%` : v.toFixed(3);
}

export default function ExperimentDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<Run | null>(null);
  const [m, setM] = useState<MetricsResponse | null>(null);
  const [evals, setEvals] = useState<
    { id: string; status: string; primary_metric?: number; metrics?: Record<string, number> }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const statusRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    statusRef.current = run?.status;
  }, [run?.status]);

  function modelArtifactId(r: Run | null): string | null {
    if (!r?.artifacts) return null;
    try {
      const arr = JSON.parse(r.artifacts) as { id: string; type: string }[];
      return (arr.find((a) => a.type === 'weights') || arr[0])?.id || null;
    } catch {
      return null;
    }
  }

  useEffect(() => {
    if (!runId) return;
    const poll = async () => {
      try {
        const [runData, metricsData] = await Promise.all([
          apiGet<Run>(`/api/experiments/runs/${runId}`),
          apiGet<MetricsResponse>(`/api/experiments/runs/${runId}/metrics`),
        ]);
        setRun(runData);
        setM(metricsData);
        setLoading(false);
        const artId = modelArtifactId(runData);
        if (artId && runData.status === 'succeeded') {
          apiGet<{ evaluations?: typeof evals }>(`/api/artifacts/models/${artId}/lineage`)
            .then((d) => setEvals(d.evaluations || []))
            .catch(() => {});
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load run');
        setLoading(false);
      }
    };
    poll();
    const interval = setInterval(() => {
      const s = statusRef.current;
      if (s === 'running' || s === 'queued') poll();
    }, 3000);
    return () => clearInterval(interval);
  }, [runId]);

  async function handleExport() {
    if (!run) return;
    setExporting(true);
    try {
      const j = await apiPost<{ id: string; status: string }>(
        `/api/artifacts/models/${run.id}/export`,
        {},
      );
      setExportJobId(j.id);
    } catch (err) {
      console.error(err);
    } finally {
      setExporting(false);
    }
  }

  function handleEvaluate() {
    if (!run) return;
    const artId = modelArtifactId(run);
    const q = new URLSearchParams();
    if (artId) q.set('artifact_id', artId);
    if (run.dataset_version_id) q.set('dataset_version_id', run.dataset_version_id);
    navigate(`/evaluations/new?${q.toString()}`);
  }

  if (loading)
    return (
      <div className="py-6">
        <Loading label="Loading experiment…" />
      </div>
    );
  if (error) return <ErrorState title="Failed to load experiment" description={error} />;
  if (!run) return <ErrorState title="Run not found" />;

  let params: Record<string, unknown> = {};
  try {
    if (run.params_json) params = JSON.parse(run.params_json);
  } catch {
    /* ignore */
  }

  const metrics = m?.metrics || [];
  const summary = m?.summary || null;
  const plots = (m?.plots || []).filter((p) => p.url);
  const split = m?.split || null;
  const isActive = run.status === 'running' || run.status === 'queued';
  const activePanels = PANELS.filter((p) => p.keys.some((k) => metrics.some((d) => d[k] != null)));
  const splitTotal = split ? split.counts.train + split.counts.val + split.counts.test : 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/experiments" className="hover:text-[var(--hud-accent)] transition-colors">
            EXPERIMENTS
          </Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">
            {(run.name || run.id.slice(0, 8)).toUpperCase()}
          </span>
        </nav>
        <div className="flex items-center justify-between gap-4">
          <h1 className="flex items-center gap-2 flex-wrap">
            {run.name || `Run ${run.id.slice(0, 8)}`}
            <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            {isActive && (
              <span className="text-xs font-mono text-[var(--hud-text-muted)] pulse-active">
                ● LIVE
              </span>
            )}
          </h1>
          {run.status === 'succeeded' && (
            <div className="flex gap-2">
              <Button onClick={handleEvaluate} size="sm" variant="outline">
                Run Evaluation
              </Button>
              <Button onClick={handleExport} disabled={exporting || !!exportJobId} size="sm">
                {exporting
                  ? 'Exporting…'
                  : exportJobId
                    ? `Job ${exportJobId.slice(0, 8)}`
                    : 'Export ONNX'}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Summary tiles */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
          {['mAP50', 'mAP50_95', 'precision', 'recall', 'top1', 'top5']
            .filter((k) => summary[k] != null)
            .map((k) => (
              <div
                key={k}
                className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-3 py-2"
              >
                <div className="label-overline mb-1">{k}</div>
                <div className="text-lg font-mono text-[var(--hud-text-data)]">
                  {fmtMetric(k, summary[k]!)}
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Metric charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        {(activePanels.length ? activePanels : PANELS.slice(0, 2)).map((p) => (
          <Panel key={p.title} title={p.title}>
            <LineChart data={metrics} keys={p.keys} />
          </Panel>
        ))}
      </div>

      {/* Split + params */}
      <div className="grid gap-4 lg:grid-cols-2">
        {split && splitTotal > 0 && (
          <Panel title="Dataset Split">
            <div className="flex h-5 w-full overflow-hidden border border-[var(--hud-border-subtle)]">
              {(['train', 'val', 'test'] as const)
                .filter((k) => split.counts[k] > 0)
                .map((k) => (
                  <div
                    key={k}
                    style={{
                      width: `${(split.counts[k] / splitTotal) * 100}%`,
                      backgroundColor: SPLIT_COLORS[k],
                    }}
                    title={`${k}: ${split.counts[k]}`}
                  />
                ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs font-mono">
              {(['train', 'val', 'test'] as const).map((k) => (
                <div key={k} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-2.5 w-2.5"
                    style={{ backgroundColor: SPLIT_COLORS[k] }}
                  />
                  <span className="text-[var(--hud-text-muted)]">{k}</span>
                  <span className="text-[var(--hud-text-data)]">{split.counts[k]}</span>
                </div>
              ))}
              {split.seed != null && (
                <span className="text-[var(--hud-text-muted)]">seed {split.seed}</span>
              )}
            </div>
          </Panel>
        )}

        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
            <span className="label-overline">Parameters</span>
          </div>
          <div className="p-4 max-h-64 overflow-y-auto">
            {Object.keys(params).length === 0 ? (
              <p className="text-xs font-mono text-[var(--hud-text-muted)]">
                No parameters recorded.
              </p>
            ) : (
              <table className="w-full text-xs font-mono">
                <tbody>
                  {Object.entries(params).map(([k, v]) => (
                    <tr
                      key={k}
                      className="border-b border-[var(--hud-border-subtle)] last:border-0"
                    >
                      <td className="py-1 pr-4 text-[var(--hud-text-muted)] uppercase tracking-wide">
                        {k}
                      </td>
                      <td className="py-1 text-[var(--hud-text-data)]">{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Plots gallery */}
      {plots.length > 0 && (
        <Panel title="Plots">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {plots.map((p) => (
              <button
                key={p.file}
                type="button"
                onClick={() => setZoom(p.url || null)}
                className="border border-[var(--hud-border-subtle)] bg-[var(--hud-inset)] p-1 hover:border-[var(--hud-accent)]"
              >
                <img src={p.url || ''} alt={p.name} className="w-full h-auto" loading="lazy" />
                <div className="label-overline mt-1 text-center">{p.name}</div>
              </button>
            ))}
          </div>
        </Panel>
      )}

      {/* Evaluations of this model */}
      {run.status === 'succeeded' && (
        <Panel title="Evaluations">
          {evals.length === 0 ? (
            <p className="text-xs font-mono text-[var(--hud-text-muted)]">
              No evaluations yet. Use{' '}
              <span className="text-[var(--hud-accent)]">Run Evaluation</span> to score this model
              on the test split.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {evals.map((ev) => {
                const metric = ev.primary_metric ?? ev.metrics?.mAP50 ?? ev.metrics?.accuracy;
                return (
                  <li key={ev.id}>
                    <Link
                      to={`/evaluations/${ev.id}`}
                      className="flex items-center justify-between text-xs font-mono hover:text-[var(--hud-accent)]"
                    >
                      <span className="text-[var(--hud-text-data)]">{ev.id.slice(0, 8)}</span>
                      <Badge variant={statusVariant(ev.status)}>{ev.status}</Badge>
                      <span className="text-[var(--hud-text-muted)]">
                        {metric != null ? fmtMetric('mAP50', metric) : '—'}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      )}

      {/* Run details */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
        <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
          <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
          <span className="label-overline">Run Details</span>
        </div>
        <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <div className="label-overline mb-1">Run ID</div>
            <code className="text-[0.6875rem] font-mono text-[var(--hud-text-data)] break-all">
              {run.id}
            </code>
          </div>
          <div>
            <div className="label-overline mb-1">Status</div>
            <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
          </div>
          <div>
            <div className="label-overline mb-1">Started</div>
            <span className="text-xs font-mono text-[var(--hud-text-secondary)]">
              {new Date(run.created_at).toLocaleString()}
            </span>
          </div>
          {run.completed_at && (
            <div>
              <div className="label-overline mb-1">Completed</div>
              <span className="text-xs font-mono text-[var(--hud-text-secondary)]">
                {new Date(run.completed_at).toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {exportJobId && (
        <div className="border border-[var(--hud-success)] border-l-2 bg-[var(--hud-success-dim)] px-4 py-2.5 text-xs font-mono text-[var(--hud-success-text)]">
          ONNX export queued · JOB{' '}
          <span className="text-[var(--hud-text-data)]">{exportJobId}</span>{' '}
          <Link
            to="/artifacts"
            className="text-[var(--hud-accent)] hover:underline underline-offset-2 ml-2"
          >
            View Artifacts →
          </Link>
        </div>
      )}

      {/* Zoom lightbox */}
      {zoom && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6"
          onClick={() => setZoom(null)}
        >
          <img src={zoom} alt="plot" className="max-h-full max-w-full" />
        </div>
      )}
    </div>
  );
}
