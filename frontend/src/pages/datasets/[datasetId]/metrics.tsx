import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiGet } from '@/services/api';
import Spinner from '@/components/ui/Spinner';
import Alert from '@/components/ui/Alert';
import StatTile from '@/components/charts/StatTile';
import BarChart, { type BarDatum } from '@/components/charts/BarChart';
import Histogram from '@/components/charts/Histogram';
import DonutChart from '@/components/charts/DonutChart';
import Sparkline from '@/components/charts/Sparkline';

interface Metrics {
  total_assets: number;
  total_annotations: number;
  coverage_pct: number;
  labeled: number;
  empty_images: number;
  label_status_distribution: Record<string, number>;
  review: { unreviewed: number; approved: number; rejected: number; flagged: number };
  class_balance: {
    instances: Record<string, number>;
    images: Record<string, number>;
    imbalance_ratio: number | null;
    defined_classes: string[];
    unused_classes: string[];
  };
  annotation_types: Record<string, number>;
  per_image: { histogram: Record<string, number>; mean: number; max: number };
  box_geometry: {
    area_histogram: Record<string, number>;
    aspect_histogram: Record<string, number>;
    sampled: boolean;
  };
  resolution: {
    min_pixels: number | null;
    max_pixels: number | null;
    median_pixels: number | null;
    histogram: Record<string, number>;
    with_dimensions: number;
  };
  velocity: { date: string; count: number }[];
  split: unknown;
}

type Severity = 'high' | 'medium' | 'low';

interface Recommendation {
  id: string;
  severity: Severity;
  category: string;
  title: string;
  detail: string;
  metric?: number | string | null;
}

interface RecommendationsResponse {
  items: Recommendation[];
  generated_from_version: string | null;
}

const SEVERITY_STYLES: Record<Severity, string> = {
  high: 'border-[var(--hud-danger)] text-[var(--hud-danger)]',
  medium: 'border-[var(--hud-warning)] text-[var(--hud-warning)]',
  low: 'border-[var(--hud-info)] text-[var(--hud-info)]',
};

const toBuckets = (rec: Record<string, number>) =>
  Object.entries(rec).map(([label, value]) => ({ label, value }));

function Panel({
  title,
  children,
  hint,
}: {
  title: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <section className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] px-3 py-2">
        <span className="label-overline">{title}</span>
        {hint && (
          <span className="font-mono text-[0.625rem] text-[var(--hud-text-muted)]">{hint}</span>
        )}
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

export default function DatasetMetrics() {
  const { datasetId } = useParams();
  const [m, setM] = useState<Metrics | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    setLoading(true);
    apiGet<Metrics>(`/api/datasets/${datasetId}/metrics`)
      .then((d) => {
        setM(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load metrics'))
      .finally(() => setLoading(false));
  }, [datasetId]);

  useEffect(() => {
    if (!datasetId) return;
    apiGet<RecommendationsResponse>(`/api/datasets/${datasetId}/recommendations`)
      .then((d) => setRecs(d.items))
      .catch(() => setRecs([]));
  }, [datasetId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 font-mono text-sm text-[var(--hud-text-muted)]">
        <Spinner size={14} /> Loading metrics…
      </div>
    );
  }
  if (error || !m) {
    return (
      <div className="space-y-4">
        <Alert variant="error">{error || 'No metrics'}</Alert>
        <Link
          to={`/datasets/${datasetId}`}
          className="font-mono text-xs text-[var(--hud-accent)] hover:underline"
        >
          ← BACK TO DATASET
        </Link>
      </div>
    );
  }

  const sd = m.label_status_distribution;
  const labeled = (sd.labeled || 0) + (sd.prelabeled || 0);
  const unlabeled = (sd.unlabeled || 0) + (sd.unlabelled || 0);
  const inProgress = sd.in_progress || 0;

  const classInstances: BarDatum[] = Object.entries(m.class_balance.instances)
    .filter(([name]) => name !== '(none)')
    .map(([label, value]) => ({ label, value }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Dataset / Metrics</div>
          <h1>Dataset Metrics</h1>
        </div>
        <Link
          to={`/datasets/${datasetId}`}
          className="font-mono text-xs text-[var(--hud-accent)] hover:underline"
        >
          ← BACK TO DATASET
        </Link>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Assets" value={m.total_assets} />
        <StatTile label="Annotations" value={m.total_annotations} />
        <StatTile
          label="Coverage"
          value={`${m.coverage_pct}%`}
          tone={m.coverage_pct >= 100 ? 'success' : 'accent'}
        />
        <StatTile
          label="Empty images"
          value={m.empty_images}
          tone={m.empty_images > 0 ? 'warning' : 'default'}
        />
        <StatTile
          label="Classes"
          value={m.class_balance.defined_classes.length || classInstances.length}
        />
        <StatTile
          label="Flagged"
          value={m.review.flagged}
          tone={m.review.flagged > 0 ? 'danger' : 'default'}
        />
      </div>

      {/* Suggested improvements */}
      <Panel
        title="Suggested improvements"
        hint={recs && recs.length > 0 ? `${recs.length} item(s)` : undefined}
      >
        {recs === null ? (
          <div className="flex items-center gap-2 font-mono text-xs text-[var(--hud-text-muted)]">
            <Spinner size={12} /> Analyzing…
          </div>
        ) : recs.length === 0 ? (
          <div className="font-mono text-xs text-[var(--hud-success)]">
            No issues found — dataset looks healthy.
          </div>
        ) : (
          <ul className="space-y-2">
            {recs.map((r) => (
              <li
                key={r.id}
                className="flex items-start gap-3 border border-[var(--hud-border-subtle)] bg-[var(--hud-surface)] p-3"
              >
                <span
                  className={`mt-0.5 shrink-0 border px-1.5 py-0.5 font-mono text-[0.625rem] uppercase ${SEVERITY_STYLES[r.severity]}`}
                >
                  {r.severity}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-[var(--hud-text-primary)]">
                    {r.title}
                  </div>
                  <div className="text-xs text-[var(--hud-text-muted)]">{r.detail}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Coverage + review donuts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Label coverage">
          <DonutChart
            centerValue={`${m.coverage_pct}%`}
            centerLabel="labeled"
            segments={[
              { label: 'Labeled', value: labeled, color: 'var(--hud-success)' },
              { label: 'In progress', value: inProgress, color: 'var(--hud-warning)' },
              { label: 'Unlabeled', value: unlabeled, color: 'var(--hud-text-muted)' },
            ]}
          />
        </Panel>
        <Panel title="Review status">
          <DonutChart
            centerValue={m.review.approved + m.review.rejected + m.review.unreviewed}
            centerLabel="annotations"
            segments={[
              { label: 'Approved', value: m.review.approved, color: 'var(--hud-success)' },
              { label: 'Rejected', value: m.review.rejected, color: 'var(--hud-danger)' },
              { label: 'Unreviewed', value: m.review.unreviewed, color: 'var(--hud-text-muted)' },
            ]}
          />
        </Panel>
      </div>

      {/* Class balance */}
      <Panel
        title="Class distribution (instances)"
        hint={
          m.class_balance.imbalance_ratio
            ? `imbalance ${m.class_balance.imbalance_ratio}×`
            : undefined
        }
      >
        <BarChart data={classInstances} />
      </Panel>

      {/* Distribution grid */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel
          title="Annotations / image"
          hint={`mean ${m.per_image.mean} · max ${m.per_image.max}`}
        >
          <Histogram data={toBuckets(m.per_image.histogram)} />
        </Panel>
        <Panel title="Box area" hint={m.box_geometry.sampled ? 'sampled' : undefined}>
          <Histogram data={toBuckets(m.box_geometry.area_histogram)} color="var(--hud-info)" />
        </Panel>
        <Panel title="Image resolution" hint={`${m.resolution.with_dimensions} sized`}>
          <Histogram data={toBuckets(m.resolution.histogram)} color="var(--hud-success)" />
        </Panel>
      </div>

      {/* Annotation types + velocity */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Annotation types">
          <BarChart data={toBuckets(m.annotation_types)} />
        </Panel>
        <Panel title="Labeling velocity (30d)">
          <Sparkline data={m.velocity} />
        </Panel>
      </div>
    </div>
  );
}
