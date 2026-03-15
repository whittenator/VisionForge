import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
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

const METRIC_KEYS: Array<keyof Omit<MetricPoint, 'epoch'>> = [
  'mAP50',
  'box_loss',
  'cls_loss',
  'precision',
  'recall',
];

const COLORS = ['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6'];

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'succeeded': return 'success';
    case 'running': return 'warning';
    case 'failed': return 'danger';
    default: return 'default';
  }
}

function MetricsChart({ data, keys }: { data: MetricPoint[]; keys: string[] }) {
  if (!data.length) {
    return <p className="text-sm text-muted-foreground py-4">No metrics recorded yet…</p>;
  }

  const W = 500;
  const H = 200;
  const PAD = 40;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full border rounded-md" aria-label="Metrics chart">
        {/* X axis */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#e5e7eb" strokeWidth="1" />
        {/* Y axis */}
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#e5e7eb" strokeWidth="1" />

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
            .filter(Boolean)
            .join(' ');

          return (
            <polyline
              key={key}
              points={pts}
              fill="none"
              stroke={COLORS[ki % COLORS.length]}
              strokeWidth="2"
            />
          );
        })}

        {/* X label */}
        <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="10" fill="#9ca3af">Epoch</text>
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-2">
        {keys.map((key, ki) => (
          <div key={key} className="flex items-center gap-1 text-xs">
            <div
              className="w-3 h-0.5 rounded"
              style={{ backgroundColor: COLORS[ki % COLORS.length] }}
            />
            <span className="text-muted-foreground">{key}</span>
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

  useEffect(() => {
    runStatusRef.current = run?.status;
  }, [run?.status]);

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
      if (status === 'running' || status === 'queued') {
        poll();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [runId]);

  async function handleExport() {
    if (!run) return;
    setExporting(true);
    try {
      const j = await apiPost<{ id: string; status: string }>(
        `/api/artifacts/models/${run.id}/export`,
        {}
      );
      setExportJobId(j.id);
    } catch (err) {
      console.error(err);
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <Loading label="Loading experiment…" />;
  if (error) return <ErrorState title="Failed to load experiment" description={error} />;
  if (!run) return <ErrorState title="Run not found" />;

  let params: Record<string, unknown> = {};
  try {
    if (run.params_json) params = JSON.parse(run.params_json);
  } catch {
    // ignore
  }

  const isActive = run.status === 'running' || run.status === 'queued';
  const activeMetricKeys = METRIC_KEYS.filter((k) =>
    metrics.some((m) => (m as Record<string, number | undefined>)[k] != null)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <nav className="text-xs text-muted-foreground mb-1">
            <Link to="/experiments" className="hover:underline">Experiments</Link>
            {' / '}
            <span>{run.name || run.id.slice(0, 8)}</span>
          </nav>
          <h1 className="text-2xl font-semibold flex items-center gap-3">
            {run.name || `Run ${run.id.slice(0, 8)}`}
            <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            {isActive && (
              <span className="text-xs text-muted-foreground animate-pulse">Auto-refreshing…</span>
            )}
          </h1>
        </div>
        {run.status === 'succeeded' && (
          <Button onClick={handleExport} disabled={exporting || !!exportJobId}>
            {exporting ? 'Exporting…' : exportJobId ? `Job ${exportJobId.slice(0, 8)}` : 'Export to ONNX'}
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* Metrics chart */}
        <Card>
          <CardHeader>
            <CardTitle>Training Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            {activeMetricKeys.length > 0 ? (
              <MetricsChart data={metrics} keys={activeMetricKeys} />
            ) : (
              <MetricsChart data={metrics} keys={METRIC_KEYS as unknown as string[]} />
            )}
          </CardContent>
        </Card>

        {/* Parameters */}
        <Card>
          <CardHeader>
            <CardTitle>Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(params).length === 0 ? (
              <p className="text-sm text-muted-foreground">No parameters recorded.</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {Object.entries(params).map(([k, v]) => (
                    <tr key={k} className="border-b last:border-0">
                      <td className="py-1.5 pr-4 font-medium text-muted-foreground">{k}</td>
                      <td className="py-1.5 font-mono">{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Run details */}
      <Card>
        <CardHeader><CardTitle>Run Details</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground text-xs">Run ID</div>
              <code className="font-mono text-xs break-all">{run.id}</code>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">Status</div>
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            </div>
            <div>
              <div className="text-muted-foreground text-xs">Started</div>
              <div>{new Date(run.created_at).toLocaleString()}</div>
            </div>
            {run.completed_at && (
              <div>
                <div className="text-muted-foreground text-xs">Completed</div>
                <div>{new Date(run.completed_at).toLocaleString()}</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {exportJobId && (
        <div className="rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          ONNX export job queued:{' '}
          <code className="font-mono">{exportJobId}</code>.{' '}
          <Link to="/artifacts" className="underline">View Artifacts</Link>
        </div>
      )}
    </div>
  );
}
