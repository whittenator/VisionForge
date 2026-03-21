import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import { apiGet, apiPost, apiDelete } from '@/services/api';

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

function ConfusionMatrix({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const maxVal = Math.max(...matrix.flat().filter(v => v > 0), 1);
  const n = labels.length;
  const displayN = Math.min(n, 15);
  const displayLabels = labels.slice(0, displayN);
  const displayMatrix = matrix.slice(0, displayN).map(row => row.slice(0, displayN));

  return (
    <div className="overflow-auto">
      <div className="text-xs text-muted-foreground mb-2">Predicted →</div>
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="w-20 text-right pr-2 text-muted-foreground">Actual ↓</th>
            {displayLabels.map(l => (
              <th key={l} className="w-14 text-center pb-1 font-medium text-muted-foreground" style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)', height: '60px' }}>
                {l.slice(0, 12)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayMatrix.map((row, ri) => (
            <tr key={ri}>
              <td className="text-right pr-2 py-0.5 font-medium text-muted-foreground truncate max-w-[80px]">
                {displayLabels[ri]?.slice(0, 12)}
              </td>
              {row.map((val, ci) => {
                const intensity = val / maxVal;
                const isCorrect = ri === ci;
                const bg = val === 0 ? 'rgb(249,250,251)' : isCorrect
                  ? `rgba(34,197,94,${0.2 + intensity * 0.7})`
                  : `rgba(239,68,68,${0.1 + intensity * 0.6})`;
                return (
                  <td
                    key={ci}
                    className="w-14 h-10 text-center text-xs border border-white font-mono"
                    style={{ backgroundColor: bg, color: intensity > 0.6 ? 'white' : 'inherit' }}
                    title={`Actual: ${displayLabels[ri]} → Predicted: ${displayLabels[ci]}: ${val}`}
                  >
                    {val > 0 ? val : ''}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {n > displayN && (
        <p className="text-xs text-muted-foreground mt-2">Showing {displayN} of {n} classes</p>
      )}
    </div>
  );
}

function EvaluationPanel({ runId, runStatus }: { runId: string; runStatus: string }) {
  const [evalData, setEvalData] = useState<any>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    apiGet<any>(`/api/experiments/runs/${runId}/evaluation`)
      .then((data: any) => {
        if (data?.status !== 'not_evaluated') setEvalData(data);
      })
      .catch(() => {});
  }, [runId]);

  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const job = await apiGet<any>(`/api/jobs/${jobId}`);
        if (job.status === 'succeeded') {
          clearInterval(interval);
          setJobId(null);
          setEvaluating(false);
          const data = await apiGet<any>(`/api/experiments/runs/${runId}/evaluation`);
          if (data?.status !== 'not_evaluated') setEvalData(data);
        } else if (job.status === 'failed') {
          clearInterval(interval);
          setJobId(null);
          setEvaluating(false);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, runId]);

  async function runEvaluation() {
    setEvaluating(true);
    try {
      const result = await apiPost<any>(`/api/experiments/runs/${runId}/evaluate`, {});
      setJobId(result.job_id);
    } catch {
      setEvaluating(false);
    }
  }

  if (!evalData) {
    return (
      <Card>
        <CardHeader><CardTitle>Model Evaluation</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Run evaluation to see confusion matrix, per-class AP, and precision-recall metrics.
          </p>
          {runStatus === 'succeeded' ? (
            <Button onClick={runEvaluation} disabled={evaluating}>
              {evaluating ? (
                <span className="flex items-center gap-2"><Spinner /> Evaluating…</span>
              ) : 'Run Evaluation'}
            </Button>
          ) : (
            <p className="text-sm text-muted-foreground">Training must complete before evaluation.</p>
          )}
        </CardContent>
      </Card>
    );
  }

  const { summary, per_class, confusion_matrix } = evalData;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Evaluation Results
            <Button variant="outline" size="sm" onClick={runEvaluation} disabled={evaluating}>
              {evaluating ? 'Re-evaluating…' : 'Re-evaluate'}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {summary && [
              { label: 'mAP@50', value: summary.mAP50, pct: true, good: 0.7 },
              { label: 'mAP@50-95', value: summary.mAP50_95, pct: true, good: 0.5 },
              { label: 'Precision', value: summary.precision, pct: true, good: 0.8 },
              { label: 'Recall', value: summary.recall, pct: true, good: 0.8 },
              { label: 'F1', value: summary.f1, pct: true, good: 0.75 },
              { label: 'Speed (ms)', value: summary.speed_ms, pct: false, good: 0 },
            ].map(({ label, value, pct, good }) => (
              <div key={label} className="text-center rounded-lg border p-3">
                <div className={`text-xl font-bold ${pct && value >= good ? 'text-green-700' : pct && value < good * 0.7 ? 'text-red-700' : 'text-yellow-700'}`}>
                  {pct ? `${(value * 100).toFixed(1)}%` : value?.toFixed(1)}
                </div>
                <div className="text-xs text-muted-foreground">{label}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {per_class && per_class.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Per-Class Metrics</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase">
                    <th className="py-2 text-left font-medium">Class</th>
                    <th className="py-2 text-right font-medium">AP@50</th>
                    <th className="py-2 text-right font-medium">AP@50-95</th>
                    <th className="py-2 text-right font-medium">Precision</th>
                    <th className="py-2 text-right font-medium">Recall</th>
                  </tr>
                </thead>
                <tbody>
                  {per_class.map((cls: any) => (
                    <tr key={cls.class_name} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="py-2 font-medium">{cls.class_name}</td>
                      <td className="py-2 text-right font-mono">{(cls.ap50 * 100).toFixed(1)}%</td>
                      <td className="py-2 text-right font-mono">{(cls.ap50_95 * 100).toFixed(1)}%</td>
                      <td className="py-2 text-right font-mono">{(cls.precision * 100).toFixed(1)}%</td>
                      <td className="py-2 text-right font-mono">{(cls.recall * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {confusion_matrix && confusion_matrix.matrix && confusion_matrix.matrix.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Confusion Matrix</CardTitle></CardHeader>
          <CardContent>
            <ConfusionMatrix labels={confusion_matrix.labels} matrix={confusion_matrix.matrix} />
          </CardContent>
        </Card>
      )}
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
  const [stopMsg, setStopMsg] = useState<string | null>(null);
  const runStatusRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    runStatusRef.current = run?.status;
  }, [run?.status]);

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

  useEffect(() => {
    if (!runId) return;

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

  async function handleStop() {
    if (!run) return;
    if (!window.confirm('Stop this training run?')) return;
    try {
      await apiDelete(`/api/jobs/${run.id}`);
      setStopMsg('Cancellation requested.');
      poll();
    } catch (e) {
      console.error(e);
      setStopMsg('Stop request sent.');
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
        <div className="flex gap-2">
          {isActive && (
            <Button
              variant="outline"
              onClick={handleStop}
              className="border-red-300 text-red-600 hover:bg-red-50"
            >
              Stop Training
            </Button>
          )}
          {run.status === 'succeeded' && (
            <Button onClick={handleExport} disabled={exporting || !!exportJobId}>
              {exporting ? 'Exporting…' : exportJobId ? `Job ${exportJobId.slice(0, 8)}` : 'Export to ONNX'}
            </Button>
          )}
        </div>
      </div>

      {stopMsg && (
        <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
          {stopMsg}
        </div>
      )}

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

      {/* Evaluation Panel */}
      <EvaluationPanel runId={run.id} runStatus={run.status} />
    </div>
  );
}
