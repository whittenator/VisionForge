import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import Pager, { PaginatedResponse } from '@/components/common/Pager';
import { apiGet, apiPost } from '@/services/api';

interface AnnotationRow {
  id: string;
  asset_id: string;
  type: string;
  geometry: Record<string, unknown>;
  class_name: string | null;
  version: number;
  review_status: 'unreviewed' | 'approved' | 'rejected';
  reviewer_id: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  flagged: boolean;
  flag_reason: string | null;
  created_at: string | null;
}

interface AssetRow {
  id: string;
  uri: string;
  width: number | null;
  height: number | null;
  label_status: string;
}

interface QueueItem {
  annotation: AnnotationRow;
  asset: AssetRow;
}

interface Summary {
  unreviewed: number;
  approved: number;
  rejected: number;
  flagged: number;
  total: number;
}

interface ArtifactLite {
  id: string;
  name?: string;
  version?: number;
}

const PAGE_SIZE = 25;

export default function DatasetReviewQueue() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const versionId = searchParams.get('versionId') || '';
  const reviewStatus = (searchParams.get('status') || '') as
    | ''
    | 'unreviewed'
    | 'approved'
    | 'rejected';
  const flaggedFilter = searchParams.get('flagged') || '';

  const [items, setItems] = useState<QueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [datasetName, setDatasetName] = useState('');
  const [versions, setVersions] = useState<{ id: string; version: number }[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactLite[]>([]);
  const [mineArtifactId, setMineArtifactId] = useState('');
  const [mineRunning, setMineRunning] = useState(false);
  const [mineResult, setMineResult] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    apiGet<{
      id: string;
      name: string;
      versions: { id: string; version: number }[];
    }>(`/api/datasets/${datasetId}`)
      .then((d) => {
        setDatasetName(d.name);
        setVersions(d.versions || []);
      })
      .catch(console.error);
  }, [datasetId]);

  useEffect(() => {
    apiGet<{ items: ArtifactLite[] }>('/api/artifacts/models?page=1&page_size=200')
      .then((r) => setArtifacts(r.items || []))
      .catch(() => {});
  }, []);

  function buildQuery(extra: Record<string, string | undefined> = {}) {
    const p = new URLSearchParams();
    p.set('page', String(page));
    p.set('page_size', String(PAGE_SIZE));
    if (versionId) p.set('version_id', versionId);
    if (reviewStatus) p.set('review_status', reviewStatus);
    if (flaggedFilter) p.set('flagged', flaggedFilter);
    for (const [k, v] of Object.entries(extra)) {
      if (v) p.set(k, v);
    }
    return p.toString();
  }

  function refresh() {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      apiGet<PaginatedResponse<QueueItem>>(
        `/api/annotations/datasets/${datasetId}/review?${buildQuery()}`,
      ),
      apiGet<Summary>(
        `/api/annotations/datasets/${datasetId}/review/summary${
          versionId ? `?version_id=${versionId}` : ''
        }`,
      ),
    ])
      .then(([data, sum]) => {
        setItems(data.items);
        setTotal(data.total);
        setSummary(sum);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load queue'))
      .finally(() => setLoading(false));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(refresh, [datasetId, versionId, reviewStatus, flaggedFilter, page]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
    setPage(1);
  }

  async function reviewOne(annotationId: string, status: 'approved' | 'rejected') {
    try {
      await apiPost(`/api/annotations/${annotationId}/review`, {
        review_status: status,
      });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${status}`);
    }
  }

  async function runErrorMining() {
    if (!mineArtifactId) {
      setError('Pick a model artifact first');
      return;
    }
    if (!datasetId) return;
    let targetVersion = versionId;
    if (!targetVersion && versions.length) {
      targetVersion = versions[0].id;
    }
    if (!targetVersion) {
      setError('Pick a dataset version to mine against');
      return;
    }
    setMineRunning(true);
    setError(null);
    try {
      const res = await apiPost<{ jobId: string; status: string }>('/api/annotations/error-mine', {
        artifact_id: mineArtifactId,
        dataset_version_id: targetVersion,
      });
      setMineResult(`queued: job ${res.jobId.slice(0, 8)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to queue error mining');
    } finally {
      setMineRunning(false);
    }
  }

  const counts = summary;

  const annotations = useMemo(() => items, [items]);

  return (
    <div className="space-y-4">
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/datasets" className="hover:text-[var(--hud-accent)]">DATASETS</Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <Link
            to={`/datasets/${datasetId}`}
            className="hover:text-[var(--hud-accent)]"
          >
            {datasetName.toUpperCase() || (datasetId || '').slice(0, 8).toUpperCase()}
          </Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">REVIEW</span>
        </nav>
        <h1>Annotation Review Queue</h1>
        <p className="text-xs text-[var(--hud-text-muted)] mt-1">
          Approve or reject annotations and triage flagged items.
        </p>
      </div>

      {/* Summary chips */}
      {counts && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-px bg-[var(--hud-border-default)]">
          {[
            { label: 'TOTAL',      value: counts.total,      filter: ''            },
            { label: 'UNREVIEWED', value: counts.unreviewed, filter: 'unreviewed'  },
            { label: 'APPROVED',   value: counts.approved,   filter: 'approved'    },
            { label: 'REJECTED',   value: counts.rejected,   filter: 'rejected'    },
            { label: 'FLAGGED',    value: counts.flagged,    filter: '__flagged__' },
          ].map((c) => {
            const isActive =
              c.filter === '__flagged__' ? flaggedFilter === 'true' : reviewStatus === c.filter;
            return (
              <button
                key={c.label}
                type="button"
                onClick={() => {
                  if (c.filter === '__flagged__') {
                    setFilter('flagged', flaggedFilter === 'true' ? '' : 'true');
                  } else {
                    setFilter('status', reviewStatus === c.filter ? '' : c.filter);
                  }
                }}
                className={[
                  'bg-[var(--hud-surface)] p-3 text-left transition-colors',
                  isActive
                    ? 'border border-[var(--hud-accent)] bg-[var(--hud-elevated)]'
                    : 'hover:bg-[var(--hud-elevated)]',
                ].join(' ')}
              >
                <div className="label-overline mb-1">{c.label}</div>
                <div className="text-2xl font-mono font-semibold text-[var(--hud-text-data)]">
                  {c.value}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Filters */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3 flex flex-wrap items-end gap-3">
        <div>
          <label className="label-overline block mb-1" htmlFor="rev-version">
            Version
          </label>
          <Select
            id="rev-version"
            value={versionId}
            onChange={(e) => setFilter('versionId', e.target.value)}
          >
            <option value="">— all —</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>v{v.version}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="label-overline block mb-1" htmlFor="rev-status">
            Status
          </label>
          <Select
            id="rev-status"
            value={reviewStatus}
            onChange={(e) => setFilter('status', e.target.value)}
          >
            <option value="">— all —</option>
            <option value="unreviewed">Unreviewed</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>
        <div>
          <label className="label-overline block mb-1" htmlFor="rev-flag">
            Flagged
          </label>
          <Select
            id="rev-flag"
            value={flaggedFilter}
            onChange={(e) => setFilter('flagged', e.target.value)}
          >
            <option value="">— all —</option>
            <option value="true">Flagged</option>
            <option value="false">Clean</option>
          </Select>
        </div>

        <div className="ml-auto flex items-end gap-2">
          <div>
            <label className="label-overline block mb-1" htmlFor="rev-mine-art">
              Error mining model
            </label>
            <Select
              id="rev-mine-art"
              value={mineArtifactId}
              onChange={(e) => setMineArtifactId(e.target.value)}
            >
              <option value="">— select model —</option>
              {artifacts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name || a.id.slice(0, 8)}
                  {a.version != null ? ` v${a.version}` : ''}
                </option>
              ))}
            </Select>
          </div>
          <Button
            onClick={runErrorMining}
            disabled={mineRunning || !mineArtifactId}
            size="md"
          >
            {mineRunning ? 'Queuing…' : 'Run Error Mining'}
          </Button>
        </div>
      </div>

      {mineResult && (
        <div className="border border-[var(--hud-success)] bg-[var(--hud-success-dim)] px-3 py-2 text-xs font-mono text-[var(--hud-success-text)]">
          {mineResult} — refresh in a few minutes to see the flagged column populate.
        </div>
      )}

      {error && <ErrorState title="Review queue error" description={error} />}

      {loading ? (
        <div className="py-6"><Loading label="Loading queue…" /></div>
      ) : annotations.length === 0 ? (
        <EmptyState
          title="Queue is empty"
          description="No annotations match the current filters."
        />
      ) : (
        <>
          <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
            {annotations.map(({ annotation: ann, asset }) => (
              <div
                key={ann.id}
                className="px-3 py-2.5 flex flex-wrap items-center gap-3 hover:bg-[var(--hud-elevated)] transition-colors"
              >
                <div className="flex-1 min-w-[260px]">
                  <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="text-[var(--hud-text-muted)]">{ann.type.toUpperCase()}</span>
                    {ann.class_name && (
                      <span className="text-[var(--hud-text-primary)]">{ann.class_name}</span>
                    )}
                    {ann.flagged && (
                      <Badge variant="danger">FLAGGED</Badge>
                    )}
                    {ann.review_status === 'approved' && (
                      <Badge variant="success">APPROVED</Badge>
                    )}
                    {ann.review_status === 'rejected' && (
                      <Badge variant="danger">REJECTED</Badge>
                    )}
                  </div>
                  <div className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-0.5 truncate">
                    asset {asset.id.slice(0, 12)}… · v{ann.version}
                    {ann.flag_reason && (
                      <span className="ml-2 text-[var(--hud-danger-text)]">
                        ({ann.flag_reason})
                      </span>
                    )}
                  </div>
                </div>
                <Link
                  to={`/annotate/${ann.asset_id}`}
                  className="text-[0.6875rem] font-mono text-[var(--hud-accent)] hover:underline"
                >
                  OPEN ANNOTATOR →
                </Link>
                <div className="flex gap-1.5">
                  <Button
                    size="xs"
                    variant="success"
                    onClick={() => reviewOne(ann.id, 'approved')}
                    disabled={ann.review_status === 'approved'}
                  >
                    APPROVE
                  </Button>
                  <Button
                    size="xs"
                    variant="danger"
                    onClick={() => reviewOne(ann.id, 'rejected')}
                    disabled={ann.review_status === 'rejected'}
                  >
                    REJECT
                  </Button>
                </div>
              </div>
            ))}
          </div>
          <Pager
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
