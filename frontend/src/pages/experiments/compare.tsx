import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import { apiGet } from '@/services/api';

interface Run {
  id: string;
  name: string;
  status: string;
  params_json?: string;
  metrics_json?: string;
  created_at: string;
  completed_at?: string;
}

function parseJson(s?: string): Record<string, any> {
  try { return s ? JSON.parse(s) : {}; } catch { return {}; }
}

function statusColor(status: string) {
  switch (status) {
    case 'succeeded': return 'text-green-700';
    case 'failed': return 'text-red-700';
    case 'running': return 'text-yellow-700';
    default: return 'text-slate-600';
  }
}

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'succeeded': return 'success';
    case 'failed': return 'danger';
    case 'running': return 'warning';
    default: return 'default';
  }
}

function RunSelector({ runs, selected, onToggle }: { runs: Run[]; selected: string[]; onToggle: (id: string) => void }) {
  return (
    <Card>
      <CardHeader><CardTitle>Select Runs to Compare (max 4)</CardTitle></CardHeader>
      <CardContent>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {runs.length === 0 && (
            <p className="text-sm text-muted-foreground py-4">No runs available.</p>
          )}
          {runs.slice(0, 50).map(r => (
            <label key={r.id} className="flex items-center gap-3 p-2 rounded hover:bg-muted cursor-pointer">
              <input
                type="checkbox"
                checked={selected.includes(r.id)}
                onChange={() => onToggle(r.id)}
                disabled={!selected.includes(r.id) && selected.length >= 4}
                className="rounded"
              />
              <span className="flex-1 text-sm">{r.name || r.id.slice(0, 8)}</span>
              <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
              <span className="text-xs text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</span>
            </label>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ExperimentsCompare() {
  const [searchParams] = useSearchParams();
  const runIds = (searchParams.get('runs') || '').split(',').filter(Boolean);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [allRuns, setAllRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string[]>(runIds);

  useEffect(() => {
    apiGet<Run[]>('/api/experiments/runs')
      .then(data => { setAllRuns(Array.isArray(data) ? data : []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selected.length === 0) { setRuns([]); return; }
    Promise.all(selected.map(id => apiGet<Run>(`/api/experiments/runs/${id}`)))
      .then(results => setRuns(results.filter(Boolean) as Run[]))
      .catch(() => {});
  }, [selected]);

  function toggleRun(id: string) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 4 ? [...prev, id] : prev);
  }

  // Get all unique param/metric keys
  const allParams = Array.from(new Set(runs.flatMap(r => Object.keys(parseJson(r.params_json)))));

  // Get final metric values (last epoch for arrays, or direct values)
  function getFinalMetric(run: Run, key: string) {
    const m = parseJson(run.metrics_json);
    if (Array.isArray(m)) {
      const last = m[m.length - 1];
      return last?.[key];
    }
    return m[key];
  }

  const HIGHLIGHT_METRICS = ['mAP50', 'mAP50_95', 'precision', 'recall'];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Compare Runs {runs.length > 0 ? `(${runs.length})` : ''}</h1>
        <Link to="/experiments" className="text-sm text-blue-600 hover:underline">← All Experiments</Link>
      </div>

      {!loading && (
        <RunSelector runs={allRuns} selected={selected} onToggle={toggleRun} />
      )}

      {runs.length >= 2 && (
        <>
          {/* Metrics comparison */}
          <Card>
            <CardHeader><CardTitle>Key Metrics</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 pr-4 text-muted-foreground">Metric</th>
                      {runs.map(r => (
                        <th key={r.id} className="text-right py-2 px-3">
                          <div className="font-medium">{r.name || r.id.slice(0, 8)}</div>
                          <div className={`text-xs ${statusColor(r.status)}`}>{r.status}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {HIGHLIGHT_METRICS.map(key => {
                      const vals = runs.map(r => getFinalMetric(r, key));
                      const numVals = vals.filter((v): v is number => typeof v === 'number');
                      const best = numVals.length > 0 ? Math.max(...numVals) : null;
                      return (
                        <tr key={key} className="border-b last:border-0">
                          <td className="py-2 pr-4 font-medium">{key}</td>
                          {vals.map((v, i) => (
                            <td key={i} className={`py-2 px-3 text-right font-mono ${v === best && best !== null ? 'text-green-700 font-bold' : ''}`}>
                              {typeof v === 'number' ? (v > 1 ? v.toFixed(3) : (v * 100).toFixed(2) + '%') : '—'}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Parameters comparison */}
          {allParams.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Parameters</CardTitle></CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 pr-4 text-muted-foreground">Parameter</th>
                        {runs.map(r => (
                          <th key={r.id} className="text-right py-2 px-3 font-medium">{r.name || r.id.slice(0, 8)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {allParams.slice(0, 20).map(key => {
                        const vals = runs.map(r => parseJson(r.params_json)[key]);
                        const allSame = vals.every(v => String(v) === String(vals[0]));
                        return (
                          <tr key={key} className={`border-b last:border-0 ${!allSame ? 'bg-yellow-50' : ''}`}>
                            <td className="py-1.5 pr-4 font-medium text-muted-foreground">{key}</td>
                            {vals.map((v, i) => (
                              <td key={i} className="py-1.5 px-3 text-right font-mono text-xs">
                                {v !== undefined ? String(v) : '—'}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <p className="text-xs text-muted-foreground mt-2">Yellow rows indicate differing values.</p>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {runs.length === 1 && (
        <p className="text-sm text-muted-foreground">Select at least 2 runs to compare.</p>
      )}
    </div>
  );
}
