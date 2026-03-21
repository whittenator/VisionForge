import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
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
  created_at: string;
  completed_at?: string;
  project_id?: string;
}

interface MetricPoint {
  epoch: number;
  box_loss?: number;
  cls_loss?: number;
  mAP50?: number;
  precision?: number;
  recall?: number;
}

const METRIC_KEYS: Array<keyof Omit<MetricPoint, 'epoch'>> = ['mAP50', 'box_loss', 'cls_loss', 'precision', 'recall'];

// HUD-palette colors for chart lines (muted, not neon)
const COLORS = [
  'oklch(0.72 0.10 82)',   // amber/accent
  'oklch(0.60 0.10 155)', // success green
  'oklch(0.68 0.16 20)',  // danger-text
  'oklch(0.72 0.08 230)', // info blue
  'oklch(0.70 0.10 75)',  // warning
];

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'succeeded': return 'success';
    case 'running':   return 'warning';
    case 'failed':    return 'danger';
    default:          return 'default';
  }
}

function MetricsChart({ data, keys }: { data: MetricPoint[]; keys: string[] }) {
  if (!data.length) {
    return <p className="text-xs font-mono text-[var(--hud-text-muted)] py-4">No metrics recorded yet…</p>;
  }

  const W = 500, H = 180, PAD = 36;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label="Metrics chart" style={{ background: 'var(--hud-inset)' }}>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75, 1].map((t) => (
          <line
            key={t}
            x1={PAD} y1={PAD + (1 - t) * (H - PAD * 2)}
            x2={W - PAD} y2={PAD + (1 - t) * (H - PAD * 2)}
            stroke="var(--hud-border-subtle)" strokeWidth="1"
          />
        ))}
        {/* Axes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="var(--hud-border-default)" strokeWidth="1" />
        <line x1={PAD} y1={PAD}     x2={PAD}     y2={H - PAD} stroke="var(--hud-border-default)" strokeWidth="1" />

        {keys.map((key, ki) => {
          const vals = data.map((d) => (d as Record<string, number | undefined>)[key]).filter((v) => v != null) as number[];
          if (!vals.length) return null;
          const min = Math.min(...vals);
          const max = Math.max(...vals);
          const norm = (v: number) => (max === min ? 0.5 : (v - min) / (max - min));
          const pts = data
            .map((d, i) => {
              const val = (d as Record<string, number | undefined>)[key];
              if (val == null) return null;
              const x = PAD + (i / Math.max(data.length - 1, 1)) * (W - PAD * 2);
              const y = PAD + (1 - norm(val)) * (H - PAD * 2);
              return `${x},${y}`;
            })
            .filter(Boolean).join(' ');

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

        <text x={W / 2} y={H - 6} textAnchor="middle" fontSize="9" fill="var(--hud-text-muted)" fontFamily="monospace">
          EPOCH
        </text>
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-2">
        {keys.map((key, ki) => (
          <div key={key} className="flex items-center gap-1.5 text-xs font-mono">
            <div className="w-4 h-0.5" style={{ backgroundColor: COLORS[ki % COLORS.length] }} />
            <span className="text-[var(--hud-text-muted)]">{key}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ExperimentDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const runStatusRef = useRef<string | undefined>(undefined);

  useEffect(() => { runStatusRef.current = run?.status; }, [run?.status]);

  useEffect(() => {
    if (!runId) return;
    const poll = async () => {
      try {
        const [runData, metricsData] = await Promise.all([
          apiGet<Run>(`/api/experiments/runs/${runId}`),
          apiGet<{ metrics: MetricPoint[] }>(`/api/experiments/runs/${runId}/metrics`),
        ]);
        setRun(runData);
        setMetrics(metricsData.metrics || []);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load run');
        setLoading(false);
      }
    };
    poll();
    const interval = setInterval(() => {
      const status = runStatusRef.current;
      if (status === 'running' || status === 'queued') poll();
    }, 3000);
    return () => clearInterval(interval);
  }, [runId]);

  async function handleExport() {
    if (!run) return;
    setExporting(true);
    try {
      const j = await apiPost<{ id: string; status: string }>(`/api/artifacts/models/${run.id}/export`, {});
      setExportJobId(j.id);
    } catch (err) {
      console.error(err);
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <div className="py-6"><Loading label="Loading experiment…" /></div>;
  if (error)   return <ErrorState title="Failed to load experiment" description={error} />;
  if (!run)    return <ErrorState title="Run not found" />;

  let params: Record<string, unknown> = {};
  try { if (run.params_json) params = JSON.parse(run.params_json); } catch { /* ignore */ }

  const isActive = run.status === 'running' || run.status === 'queued';
  const activeMetricKeys = METRIC_KEYS.filter((k) =>
    metrics.some((m) => (m as Record<string, number | undefined>)[k] != null)
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/experiments" className="hover:text-[var(--hud-accent)] transition-colors">EXPERIMENTS</Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">{(run.name || run.id.slice(0, 8)).toUpperCase()}</span>
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
            <Button onClick={handleExport} disabled={exporting || !!exportJobId} size="sm">
              {exporting ? 'Exporting…' : exportJobId ? `Job ${exportJobId.slice(0, 8)}` : 'Export ONNX'}
            </Button>
          )}
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        {/* Metrics chart */}
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="label-overline">Training Metrics</span>
          </div>
          <div className="p-4">
            <MetricsChart
              data={metrics}
              keys={(activeMetricKeys.length > 0 ? activeMetricKeys : METRIC_KEYS) as unknown as string[]}
            />
          </div>
        </div>

        {/* Parameters */}
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
            <span className="label-overline">Parameters</span>
          </div>
          <div className="p-4">
            {Object.keys(params).length === 0 ? (
              <p className="text-xs font-mono text-[var(--hud-text-muted)]">No parameters recorded.</p>
            ) : (
              <table className="w-full text-xs font-mono">
                <tbody>
                  {Object.entries(params).map(([k, v]) => (
                    <tr key={k} className="border-b border-[var(--hud-border-subtle)] last:border-0">
                      <td className="py-1.5 pr-4 text-[var(--hud-text-muted)] uppercase tracking-wide">{k}</td>
                      <td className="py-1.5 text-[var(--hud-text-data)]">{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Run details */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
        <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
          <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
          <span className="label-overline">Run Details</span>
        </div>
        <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <div className="label-overline mb-1">Run ID</div>
            <code className="text-[0.6875rem] font-mono text-[var(--hud-text-data)] break-all">{run.id}</code>
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
          ONNX export queued · JOB <span className="text-[var(--hud-text-data)]">{exportJobId}</span>{' '}
          <Link to="/artifacts" className="text-[var(--hud-accent)] hover:underline underline-offset-2 ml-2">
            View Artifacts →
          </Link>
        </div>
      )}
    </div>
  );
}
