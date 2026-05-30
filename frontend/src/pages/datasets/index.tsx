import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import Pager, { PaginatedResponse } from '@/components/common/Pager';
import { apiGet } from '@/services/api';

type DatasetStatus = 'ready' | 'annotating' | 'review';

interface Dataset {
  id: string;
  name: string;
  asset_count: number;
  latest_version?: number;
  latest_version_id?: string;
  project_id?: string;
  project_name?: string;
  task_type?: 'detect' | 'classify' | null;
  coverage_pct?: number;
  status?: DatasetStatus;
  created_at: string;
}

const PAGE_SIZE = 24;

// 5-column grid shared by the table header and every body row.
const GRID = 'grid items-center gap-3.5 [grid-template-columns:2.2fr_0.8fr_1fr_1.4fr_1.2fr]';

const STATUS_META: Record<
  DatasetStatus,
  { variant: 'success' | 'warning' | 'info'; label: string }
> = {
  ready: { variant: 'success', label: '● READY' },
  annotating: { variant: 'warning', label: 'ANNOTATING' },
  review: { variant: 'info', label: 'IN REVIEW' },
};

/** Short, stable, monospace id chip in the spirit of the design (`ds_4471`). */
function shortId(id: string): string {
  return `ds_${id.replace(/-/g, '').slice(0, 4)}`;
}

function CoverageCell({ dataset }: { dataset: Dataset }) {
  const pct = Math.max(0, Math.min(100, Math.round(dataset.coverage_pct ?? 0)));
  const version = dataset.latest_version;
  const full = pct >= 100;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-[0.625rem] font-mono">
        <span className="text-[var(--hud-text-muted)]">
          {version != null ? `v${version}` : '—'}
        </span>
        <span className="text-[var(--hud-text-data)]">{pct}%</span>
      </div>
      <div className="h-[3px] w-full bg-[var(--hud-inset)]">
        <div
          className="h-full transition-all duration-100"
          style={{
            width: `${pct}%`,
            backgroundColor: full ? 'var(--hud-success)' : 'var(--hud-accent)',
          }}
        />
      </div>
    </div>
  );
}

function DatasetRow({ dataset }: { dataset: Dataset }) {
  const status = STATUS_META[dataset.status ?? 'ready'] ?? STATUS_META.ready;
  return (
    <div className={`${GRID} bg-[var(--hud-surface)] px-4 py-3 transition-colors duration-100 hover:bg-[var(--hud-elevated)]`}>
      {/* Dataset */}
      <div className="min-w-0">
        <Link
          to={`/datasets/${dataset.id}`}
          className="block truncate font-mono text-[0.8125rem] text-[var(--hud-text-primary)] hover:text-[var(--hud-accent)] transition-colors"
        >
          {dataset.name}
        </Link>
        <div className="truncate font-mono text-[0.625rem] text-[var(--hud-text-muted)]">
          {shortId(dataset.id)}
        </div>
      </div>

      {/* Task */}
      <div>
        {dataset.task_type ? (
          <span className="inline-flex border border-[var(--hud-border-default)] px-1.5 py-px font-mono text-[0.625rem] uppercase tracking-[0.12em] text-[var(--hud-text-accent)]">
            {dataset.task_type}
          </span>
        ) : (
          <span className="font-mono text-[0.625rem] text-[var(--hud-text-muted)]">—</span>
        )}
      </div>

      {/* Assets */}
      <div className="font-mono text-xs text-[var(--hud-text-data)]">
        {dataset.asset_count.toLocaleString()}
      </div>

      {/* Coverage */}
      <CoverageCell dataset={dataset} />

      {/* Status + action */}
      <div className="flex items-center justify-end gap-2">
        <Badge variant={status.variant}>{status.label}</Badge>
        {dataset.asset_count > 0 ? (
          <Link
            to={`/datasets/${dataset.id}/annotate`}
            className="inline-flex h-6 items-center border border-[var(--hud-border-strong)] px-2 font-mono text-xs uppercase tracking-wide text-[var(--hud-text-primary)] transition-colors duration-100 hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)]"
          >
            ANNOTATE
          </Link>
        ) : (
          <span className="inline-flex h-6 items-center px-2 font-mono text-xs text-[var(--hud-text-muted)]">
            —
          </span>
        )}
      </div>
    </div>
  );
}

export default function DatasetsIndex() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') || '';

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (projectId) params.set('project_id', projectId);
    apiGet<PaginatedResponse<Dataset> | Dataset[]>(`/api/datasets?${params.toString()}`)
      .then((data) => {
        // Tolerate both the paginated envelope and a bare array.
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? items.length);
        setDatasets(items);
        setTotal(count);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load datasets'))
      .finally(() => setLoading(false));
  }, [projectId, page]);

  const uploadTo = projectId ? `/datasets/upload?projectId=${projectId}` : '/datasets/upload';

  return (
    <div className="space-y-4.5">
      {/* PageHeader */}
      <div className="flex items-end justify-between border-b border-[var(--hud-border-subtle)] pb-3.5">
        <div>
          <div className="label-overline mb-1 flex items-center gap-2">
            {projectId ? '// Projects / Datasets' : '// Datasets'}
            {projectId && (
              <Link
                to="/datasets"
                className="font-mono text-[var(--hud-accent)] hover:underline"
              >
                CLEAR ×
              </Link>
            )}
          </div>
          <h1>Datasets</h1>
          <p className="mt-1 text-xs text-[var(--hud-text-muted)]">
            Versioned image collections and their annotation coverage.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/datasets/import"
            className="inline-flex h-8 items-center border border-[var(--hud-border-strong)] px-3 font-mono text-xs uppercase tracking-wide text-[var(--hud-text-primary)] transition-colors duration-100 hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)]"
          >
            IMPORT COCO/YOLO
          </Link>
          <Link
            to={uploadTo}
            className="inline-flex h-8 items-center border border-[var(--hud-accent)] bg-[var(--hud-accent)] px-3 font-mono text-xs font-medium uppercase tracking-wide text-[oklch(0.10_0.008_240)] transition-colors duration-100 hover:bg-[var(--hud-accent-hover)] hover:border-[var(--hud-accent-hover)]"
          >
            + UPLOAD DATASET
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="py-6">
          <Loading label="Loading datasets…" />
        </div>
      ) : error ? (
        <ErrorState title="Failed to load datasets" description={error} />
      ) : datasets.length === 0 ? (
        <EmptyState
          title="No datasets yet"
          description="Upload images or annotation files to create a dataset."
        >
          <Link
            to="/datasets/upload"
            className="inline-flex h-7 items-center border border-[var(--hud-accent)] px-3 font-mono text-xs text-[var(--hud-accent)] transition-colors duration-100 hover:bg-[var(--hud-accent-dim)]"
          >
            Upload Dataset →
          </Link>
        </EmptyState>
      ) : (
        <>
          {/* Table */}
          <div className="border border-[var(--hud-border-default)]">
            {/* Header row */}
            <div className={`${GRID} border-b border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-4 py-2`}>
              <span className="label-overline">Dataset</span>
              <span className="label-overline">Task</span>
              <span className="label-overline">Assets</span>
              <span className="label-overline">Coverage</span>
              <span className="label-overline text-right">Status</span>
            </div>
            {/* Body rows — hairline seams via a 1px gap over the subtle border color */}
            <div className="flex flex-col gap-px bg-[var(--hud-border-subtle)]">
              {datasets.map((ds) => (
                <DatasetRow key={ds.id} dataset={ds} />
              ))}
            </div>
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
