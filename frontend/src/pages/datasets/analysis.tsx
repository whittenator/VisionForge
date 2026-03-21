import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import { apiGet } from '@/services/api';

interface Stats {
  total: number;
  labeled: number;
  unlabeled: number;
  in_progress: number;
  prelabeled?: number;
  coverage_pct: number;
  label_status_distribution?: Record<string, number>;
  class_distribution?: Record<string, number>;
}

interface DatasetInfo {
  id: string;
  name: string;
  description?: string;
}

export default function DatasetAnalysis() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [stats, setStats] = useState<Stats | null>(null);
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    Promise.all([
      apiGet<DatasetInfo>(`/api/datasets/${datasetId}`),
      apiGet<Stats>(`/api/datasets/${datasetId}/stats`),
    ])
      .then(([ds, st]) => {
        setDataset(ds);
        setStats(st);
      })
      .catch((err) => setError(err.message || 'Failed to load stats'))
      .finally(() => setLoading(false));
  }, [datasetId]);

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>;
  if (error) return <div className="text-red-600 p-4">{error}</div>;
  if (!stats) return null;

  const classEntries = Object.entries(stats.class_distribution || {}).sort((a, b) => b[1] - a[1]);
  const maxCount = classEntries.length > 0 ? classEntries[0][1] : 1;
  const avgCount =
    classEntries.length > 0
      ? classEntries.reduce((s, [, v]) => s + v, 0) / classEntries.length
      : 0;

  // Donut chart data
  const donutData = [
    { label: 'Labeled', value: stats.labeled, color: '#22c55e' },
    { label: 'In Progress', value: stats.in_progress, color: '#f59e0b' },
    { label: 'Unlabeled', value: stats.unlabeled, color: '#ef4444' },
    { label: 'Prelabeled', value: stats.prelabeled || 0, color: '#3b82f6' },
  ].filter((d) => d.value > 0);
  const donutTotal = donutData.reduce((s, d) => s + d.value, 0) || 1;

  // Health warnings
  const warnings: string[] = [];
  if (stats.coverage_pct < 50)
    warnings.push(`Low annotation coverage: ${stats.coverage_pct.toFixed(1)}% labeled`);
  const imbalancedClasses = classEntries.filter(
    ([, v]) => v < avgCount * 0.1 && avgCount > 0,
  );
  if (imbalancedClasses.length > 0)
    warnings.push(
      `${imbalancedClasses.length} class(es) severely underrepresented: ${imbalancedClasses.map(([k]) => k).join(', ')}`,
    );
  if (stats.total === 0) warnings.push('No assets in this dataset');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <nav className="text-xs text-muted-foreground mb-1">
            <Link to="/datasets" className="hover:underline">
              Datasets
            </Link>
            {' / '}
            <Link to={`/datasets/${datasetId}/assets`} className="hover:underline">
              {dataset?.name || datasetId}
            </Link>
            {' / '}
            <span>Analysis</span>
          </nav>
          <h1 className="text-2xl font-semibold">Dataset Analysis</h1>
          {dataset?.description && (
            <p className="text-sm text-muted-foreground mt-1">{dataset.description}</p>
          )}
        </div>
        <Link to={`/datasets/${datasetId}/assets`}>
          <button className="text-sm text-blue-600 hover:underline">← Asset Browser</button>
        </Link>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Assets', value: stats.total, color: 'text-slate-800' },
          { label: 'Labeled', value: stats.labeled, color: 'text-green-700' },
          {
            label: 'Coverage',
            value: `${(stats.coverage_pct || 0).toFixed(1)}%`,
            color:
              stats.coverage_pct >= 80
                ? 'text-green-700'
                : stats.coverage_pct >= 50
                  ? 'text-yellow-700'
                  : 'text-red-700',
          },
          { label: 'Classes', value: classEntries.length, color: 'text-blue-700' },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <CardContent className="pt-4 text-center">
              <div className={`text-3xl font-bold ${color}`}>{value}</div>
              <div className="text-sm text-muted-foreground mt-1">{label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Class distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Class Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {classEntries.length === 0 ? (
              <p className="text-sm text-muted-foreground">No annotations yet</p>
            ) : (
              <div className="space-y-2">
                {classEntries.map(([cls, count]) => {
                  const pct = Math.round((count / maxCount) * 100);
                  const isLow = avgCount > 0 && count < avgCount * 0.1;
                  const totalAnns = classEntries.reduce((s, [, v]) => s + v, 0) || 1;
                  return (
                    <div key={cls}>
                      <div className="flex justify-between text-sm mb-0.5">
                        <span className={`font-medium ${isLow ? 'text-red-600' : ''}`}>
                          {isLow ? '⚠ ' : ''}
                          {cls}
                        </span>
                        <span className="text-muted-foreground">
                          {count} ({((count / totalAnns) * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-3 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${isLow ? 'bg-red-400' : 'bg-blue-500'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Label status */}
        <Card>
          <CardHeader>
            <CardTitle>Label Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {donutData.map(({ label, value, color }) => {
                const pct = ((value / donutTotal) * 100).toFixed(1);
                return (
                  <div key={label}>
                    <div className="flex justify-between text-sm mb-0.5">
                      <span className="flex items-center gap-2">
                        <span
                          className="inline-block w-3 h-3 rounded-full"
                          style={{ backgroundColor: color }}
                        />
                        {label}
                      </span>
                      <span className="text-muted-foreground">
                        {value} ({pct}%)
                      </span>
                    </div>
                    <div className="h-3 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, backgroundColor: color }}
                      />
                    </div>
                  </div>
                );
              })}

              {/* Coverage gauge */}
              <div className="pt-2 border-t">
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">Overall Coverage</span>
                  <span className="font-bold text-lg">
                    {(stats.coverage_pct || 0).toFixed(1)}%
                  </span>
                </div>
                <div className="h-4 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(stats.coverage_pct || 0, 100)}%`,
                      backgroundColor:
                        stats.coverage_pct >= 80
                          ? '#22c55e'
                          : stats.coverage_pct >= 50
                            ? '#f59e0b'
                            : '#ef4444',
                    }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Health warnings */}
      <Card>
        <CardHeader>
          <CardTitle>Dataset Health</CardTitle>
        </CardHeader>
        <CardContent>
          {warnings.length === 0 ? (
            <div className="flex items-center gap-2 text-green-700">
              <span className="text-xl">✓</span>
              <span className="font-medium">Dataset looks healthy</span>
            </div>
          ) : (
            <ul className="space-y-2">
              {warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-amber-700">
                  <span className="text-base mt-0.5">⚠</span>
                  <span className="text-sm">{w}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 pt-4 border-t flex gap-3">
            <Link to={`/datasets/${datasetId}/assets?status=unlabeled`}>
              <button className="text-sm text-blue-600 hover:underline">
                View unlabeled assets →
              </button>
            </Link>
            {stats.unlabeled > 0 && (
              <Link to={`/datasets/upload?datasetId=${datasetId}`}>
                <button className="text-sm text-blue-600 hover:underline">
                  Upload more assets →
                </button>
              </Link>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
