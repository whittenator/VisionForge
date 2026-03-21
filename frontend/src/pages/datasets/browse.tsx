import React, { useState, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { apiGet, apiPost } from '@/services/api';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';

interface Asset {
  id: string;
  uri: string;
  download_url?: string;
  label_status: string;
  mime_type: string;
  width?: number;
  height?: number;
  created_at: string;
}

interface AssetsResponse {
  items?: Asset[];
  total?: number;
  assets?: Asset[];
}

interface DatasetInfo {
  id: string;
  name: string;
}

interface DatasetStats {
  total: number;
  labeled: number;
  unlabeled: number;
  in_progress: number;
  coverage_pct: number;
  class_distribution?: Record<string, number>;
}

const STATUS_COLORS: Record<string, string> = {
  unlabeled: 'bg-red-100 text-red-700 border-red-200',
  in_progress: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  labeled: 'bg-green-100 text-green-700 border-green-200',
  prelabeled: 'bg-blue-100 text-blue-700 border-blue-200',
};

const STATUS_BORDER: Record<string, string> = {
  unlabeled: 'border-red-400',
  in_progress: 'border-yellow-400',
  labeled: 'border-green-400',
  prelabeled: 'border-blue-400',
};

const PAGE_SIZE = 24;

export default function AssetBrowser() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const filterStatus = searchParams.get('status') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);
  const offset = (page - 1) * PAGE_SIZE;

  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [prelabelMsg, setPrelabelMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    apiGet<DatasetInfo>(`/api/datasets/${datasetId}`)
      .then(setDataset)
      .catch(() => {});
    apiGet<DatasetStats>(`/api/datasets/${datasetId}/stats`)
      .then(setStats)
      .catch(() => {});
  }, [datasetId]);

  useEffect(() => {
    if (!datasetId) return;
    setLoading(true);
    const qs = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (filterStatus) qs.set('label_status', filterStatus);
    apiGet<AssetsResponse>(`/api/datasets/${datasetId}/assets?${qs}`)
      .then((data) => {
        const items = Array.isArray(data) ? data : data.items || data.assets || [];
        setAssets(items as Asset[]);
        setTotal(
          typeof (data as { total?: number }).total === 'number'
            ? (data as { total: number }).total
            : items.length,
        );
      })
      .catch(() => setAssets([]))
      .finally(() => setLoading(false));
  }, [datasetId, filterStatus, offset]);

  function setFilter(status: string) {
    setSearchParams(status ? { status } : {});
  }

  function setPage(p: number) {
    const params: Record<string, string> = { page: String(p) };
    if (filterStatus) params.status = filterStatus;
    setSearchParams(params);
  }

  async function triggerPrelabel() {
    setPrelabelMsg(null);
    try {
      await apiPost('/api/al/prelabel', { dataset_id: datasetId });
      setPrelabelMsg('Pre-labeling job queued');
    } catch {
      setPrelabelMsg('Pre-labeling requires a trained model. Train a model first.');
    }
    setTimeout(() => setPrelabelMsg(null), 4000);
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <nav className="text-xs text-muted-foreground mb-1">
            <Link to="/datasets" className="hover:underline">
              Datasets
            </Link>
            {' / '}
            <span>{dataset?.name || datasetId}</span>
            {' / '}
            <span>Assets</span>
          </nav>
          <h1 className="text-2xl font-semibold">Asset Browser</h1>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Link to={`/datasets/${datasetId}/analysis`}>
            <Button variant="outline" size="sm">
              Dataset Analysis
            </Button>
          </Link>
          <Link to={`/datasets/version?datasetId=${datasetId}`}>
            <Button variant="outline" size="sm">
              Create Snapshot
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={triggerPrelabel}>
            Auto Pre-label
          </Button>
        </div>
      </div>

      {prelabelMsg && (
        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          {prelabelMsg}
        </div>
      )}

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: 'Total', value: stats.total, color: 'text-slate-700' },
            { label: 'Labeled', value: stats.labeled, color: 'text-green-700' },
            { label: 'In Progress', value: stats.in_progress, color: 'text-yellow-700' },
            { label: 'Unlabeled', value: stats.unlabeled, color: 'text-red-700' },
            {
              label: 'Coverage',
              value: `${stats.coverage_pct?.toFixed(1) ?? 0}%`,
              color: 'text-blue-700',
            },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-lg border bg-card p-3 text-center">
              <div className={`text-xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-muted-foreground">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap">
        {['', 'unlabeled', 'in_progress', 'labeled', 'prelabeled'].map((s) => (
          <button
            key={s || 'all'}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-full text-sm border transition-colors ${
              filterStatus === s
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-background hover:bg-muted border-border'
            }`}
          >
            {s === '' ? 'All' : s.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          </button>
        ))}
        <span className="ml-auto text-sm text-muted-foreground self-center">
          {total} asset{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : assets.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg font-medium">No assets found</p>
          <p className="text-sm mt-1">
            {filterStatus ? 'Try a different filter' : 'Upload assets to get started'}
          </p>
          <Link to={`/datasets/upload?datasetId=${datasetId}`} className="mt-4 inline-block">
            <Button size="sm">Upload Assets</Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {assets.map((asset) => (
            <AssetCard key={asset.id} asset={asset} datasetId={datasetId!} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            ← Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages} &nbsp;·&nbsp; Showing {offset + 1}–
            {Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next →
          </Button>
        </div>
      )}
    </div>
  );
}

function AssetCard({ asset, datasetId }: { asset: Asset; datasetId: string }) {
  const [imgError, setImgError] = useState(false);
  const statusKey = asset.label_status || 'unlabeled';
  const borderColor = STATUS_BORDER[statusKey] || 'border-slate-300';
  const badgeColor = STATUS_COLORS[statusKey] || 'bg-slate-100 text-slate-700';

  return (
    <div
      className={`group relative rounded-lg border-2 ${borderColor} overflow-hidden bg-slate-50 hover:shadow-md transition-shadow`}
    >
      {/* Image */}
      <div className="aspect-square relative bg-slate-100">
        {!imgError && asset.download_url ? (
          <img
            src={asset.download_url}
            alt={asset.id}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400">
            <div className="text-center">
              <div className="text-2xl mb-1">🖼</div>
              <div className="text-xs font-mono truncate px-1">{asset.id.slice(0, 8)}</div>
            </div>
          </div>
        )}
        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <Link
            to={`/annotate/${asset.id}?datasetId=${datasetId}`}
            className="bg-white text-slate-900 text-xs font-semibold px-3 py-1.5 rounded hover:bg-slate-100 transition-colors"
          >
            Annotate
          </Link>
        </div>
      </div>
      {/* Footer */}
      <div className="px-2 py-1.5">
        <span className={`inline-block text-xs px-1.5 py-0.5 rounded border ${badgeColor}`}>
          {statusKey.replace('_', ' ')}
        </span>
        {asset.width && asset.height && (
          <span className="ml-1 text-xs text-muted-foreground">
            {asset.width}×{asset.height}
          </span>
        )}
      </div>
    </div>
  );
}
