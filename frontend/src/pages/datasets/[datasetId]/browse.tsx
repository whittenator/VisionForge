import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import Pager from '@/components/common/Pager';
import { apiGet, apiPost } from '@/services/api';

interface AssetItem {
  id: string;
  uri: string;
  download_url: string;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  label_status: string;
  split: string | null;
  created_at: string | null;
}

interface AssetPage {
  items: AssetItem[];
  total: number;
  limit: number;
  offset: number;
}

interface DatasetVersion {
  id: string;
  version: number;
}

interface DatasetDetail {
  id: string;
  name: string;
  versions: DatasetVersion[];
}

interface JobStatus {
  jobId: string;
  status: string;
  progress: number;
}

const PAGE_SIZE = 24;

const LABEL_STATUS_OPTIONS = [
  { value: '', label: '— all —' },
  { value: 'unlabeled', label: 'Unlabeled' },
  { value: 'labeled', label: 'Labeled' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'prelabeled', label: 'Prelabeled' },
];

const SPLIT_OPTIONS = [
  { value: '', label: '— all —' },
  { value: 'train', label: 'Train' },
  { value: 'val', label: 'Val' },
  { value: 'test', label: 'Test' },
];

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'info' {
  switch (status) {
    case 'labeled':
      return 'success';
    case 'prelabeled':
      return 'info';
    case 'in_progress':
      return 'warning';
    default:
      return 'default';
  }
}

export default function DatasetBrowse() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const versionId = searchParams.get('versionId') || '';
  const labelStatus = searchParams.get('label_status') || '';
  const split = searchParams.get('split') || '';

  const [datasetName, setDatasetName] = useState('');
  const [versions, setVersions] = useState<DatasetVersion[]>([]);

  const [items, setItems] = useState<AssetItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [prelabeling, setPrelabeling] = useState(false);
  const [prelabelMsg, setPrelabelMsg] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    apiGet<DatasetDetail>(`/api/datasets/${datasetId}`)
      .then((d) => {
        setDatasetName(d.name);
        setVersions(d.versions || []);
      })
      .catch((err) => console.warn('Failed to load dataset metadata', err));
  }, [datasetId]);

  const refresh = useCallback(() => {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', String((page - 1) * PAGE_SIZE));
    if (versionId) params.set('version_id', versionId);
    if (labelStatus) params.set('label_status', labelStatus);
    if (split) params.set('split', split);
    apiGet<AssetPage>(`/api/datasets/${datasetId}/assets?${params.toString()}`)
      .then((data) => {
        setItems(data.items || []);
        setTotal(data.total || 0);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load assets'))
      .finally(() => setLoading(false));
  }, [datasetId, versionId, labelStatus, split, page]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Stop any in-flight poll when the page unmounts.
  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, []);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
    setPage(1);
  }

  function pollJob(jobId: string) {
    apiGet<JobStatus>(`/api/jobs/${jobId}`)
      .then((job) => {
        const pct = Math.round((job.progress || 0) * 100);
        if (job.status === 'succeeded') {
          setPrelabelMsg(`Prelabel job ${jobId.slice(0, 8)} complete — refreshing grid.`);
          setPrelabeling(false);
          refresh();
          return;
        }
        if (job.status === 'failed' || job.status === 'cancelled') {
          setPrelabelMsg(`Prelabel job ${jobId.slice(0, 8)} ${job.status}.`);
          setPrelabeling(false);
          return;
        }
        setPrelabelMsg(`Prelabeling… job ${jobId.slice(0, 8)} (${job.status}, ${pct}%)`);
        pollRef.current = window.setTimeout(() => pollJob(jobId), 2000);
      })
      .catch((err) => {
        setPrelabelMsg(err instanceof Error ? err.message : 'Lost track of prelabel job');
        setPrelabeling(false);
      });
  }

  async function runPrelabel() {
    if (!datasetId) return;
    setPrelabeling(true);
    setPrelabelMsg('Dispatching prelabel job…');
    try {
      const params = new URLSearchParams();
      if (versionId) params.set('version_id', versionId);
      const qs = params.toString();
      const res = await apiPost<{ jobId: string; status: string }>(
        `/api/datasets/${datasetId}/prelabel${qs ? `?${qs}` : ''}`,
      );
      setPrelabelMsg(`Queued prelabel job ${res.jobId.slice(0, 8)}…`);
      pollJob(res.jobId);
    } catch (err) {
      setPrelabelMsg(err instanceof Error ? err.message : 'Failed to start prelabeling');
      setPrelabeling(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/datasets" className="hover:text-[var(--hud-accent)]">
            DATASETS
          </Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <Link to={`/datasets/${datasetId}`} className="hover:text-[var(--hud-accent)]">
            {datasetName.toUpperCase() || (datasetId || '').slice(0, 8).toUpperCase()}
          </Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">BROWSE</span>
        </nav>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1>Asset Gallery</h1>
            <p className="text-xs text-[var(--hud-text-muted)] mt-1">
              Browse, filter, and prelabel the images in this dataset.
            </p>
          </div>
          <Button onClick={runPrelabel} disabled={prelabeling}>
            {prelabeling ? 'Prelabeling…' : 'Prelabel dataset'}
          </Button>
        </div>
      </div>

      {prelabelMsg && (
        <div className="border border-[var(--hud-info)] bg-[var(--hud-info-dim)] px-3 py-2 text-xs font-mono text-[var(--hud-info-text)]">
          {prelabelMsg}
        </div>
      )}

      {/* Filters */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3 flex flex-wrap items-end gap-3">
        {versions.length > 0 && (
          <div>
            <label className="label-overline block mb-1" htmlFor="br-version">
              Version
            </label>
            <Select
              id="br-version"
              value={versionId}
              onChange={(e) => setFilter('versionId', e.target.value)}
            >
              <option value="">— all —</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version}
                </option>
              ))}
            </Select>
          </div>
        )}
        <div>
          <label className="label-overline block mb-1" htmlFor="br-status">
            Label status
          </label>
          <Select
            id="br-status"
            value={labelStatus}
            onChange={(e) => setFilter('label_status', e.target.value)}
          >
            {LABEL_STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="label-overline block mb-1" htmlFor="br-split">
            Split
          </label>
          <Select id="br-split" value={split} onChange={(e) => setFilter('split', e.target.value)}>
            {SPLIT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {error && <ErrorState title="Gallery error" description={error} />}

      {loading ? (
        <div className="py-6">
          <Loading label="Loading assets…" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState title="No assets" description="No assets match the current filters." />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {items.map((a) => (
              <Link
                key={a.id}
                to={`/annotate/${a.id}`}
                className="group relative block border border-[var(--hud-border-default)] bg-[var(--hud-inset)] overflow-hidden hover:border-[var(--hud-accent)] transition-colors"
                title={a.uri}
              >
                <div className="aspect-square w-full overflow-hidden">
                  <img
                    src={a.download_url}
                    alt={a.uri.split('/').slice(-1)[0] || a.id}
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  />
                </div>
                <div className="absolute top-1 left-1">
                  <Badge variant={statusVariant(a.label_status)}>
                    {(a.label_status || 'unlabeled').toUpperCase()}
                  </Badge>
                </div>
                {a.split && (
                  <div className="absolute top-1 right-1 text-[0.625rem] font-mono px-1 py-0.5 bg-[var(--hud-surface)]/80 text-[var(--hud-text-muted)] uppercase">
                    {a.split}
                  </div>
                )}
                <div className="absolute bottom-0 inset-x-0 px-1.5 py-1 bg-[var(--hud-surface)]/85 text-[0.625rem] font-mono text-[var(--hud-text-secondary)] truncate">
                  {a.uri.split('/').slice(-1)[0] || a.id.slice(0, 12)}
                </div>
              </Link>
            ))}
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
