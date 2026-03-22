import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface DatasetInfo {
  id: string;
  name: string;
  latest_version_id?: string;
}

interface AssetItem {
  id: string;
  label_status: string;
}

/**
 * Gateway page: given a datasetId, find the first unlabeled asset and redirect
 * to the annotator. Shows a queue-style picker if multiple assets exist.
 */
export default function DatasetAnnotateGateway() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const navigate = useNavigate();
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    async function load() {
      try {
        // Fetch dataset to get latest_version_id
        const ds = await apiGet<DatasetInfo & { versions?: { id: string }[] }>(
          `/api/datasets/${datasetId}`
        );
        setDataset(ds);

        const versionId = ds.latest_version_id ?? ds.versions?.[0]?.id;
        if (!versionId) {
          setAssets([]);
          setLoading(false);
          return;
        }

        // Prefer unlabeled assets first
        const result = await apiGet<{ items: AssetItem[]; total: number }>(
          `/api/datasets/${datasetId}/assets?version_id=${versionId}&label_status=unlabeled&limit=50`
        );
        const items = result.items || [];

        if (items.length === 0) {
          // Fall back to all assets regardless of status
          const all = await apiGet<{ items: AssetItem[] }>(
            `/api/datasets/${datasetId}/assets?version_id=${versionId}&limit=50`
          );
          setAssets(all.items || []);
        } else {
          setAssets(items);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dataset');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [datasetId]);

  // Auto-redirect when there is exactly one asset
  useEffect(() => {
    if (!loading && assets.length === 1) {
      navigate(`/annotate/${assets[0].id}`, { replace: true });
    }
  }, [loading, assets, navigate]);

  if (loading) return <div className="py-6"><Loading label="Finding assets to annotate…" /></div>;
  if (error) return <ErrorState title="Failed to load dataset" description={error} />;

  if (assets.length === 0) {
    return (
      <EmptyState
        title="No assets to annotate"
        description="Upload images to this dataset first, then come back to annotate."
      >
        <Link
          to={`/datasets/upload?datasetId=${datasetId}`}
          className="inline-flex items-center h-7 px-3 text-xs font-mono border border-[var(--hud-accent)] text-[var(--hud-accent)] hover:bg-[var(--hud-accent-dim)] transition-colors"
        >
          Upload Assets →
        </Link>
      </EmptyState>
    );
  }

  // Show asset picker for multiple assets
  return (
    <div className="space-y-4">
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <div className="label-overline mb-0.5">
          // {dataset?.name} / Annotate
        </div>
        <h1>Select Asset to Annotate</h1>
      </div>

      <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
        {assets.map((a) => (
          <Link
            key={a.id}
            to={`/annotate/${a.id}`}
            className="flex items-center justify-between px-4 py-3 hover:bg-[var(--hud-elevated)] transition-colors group"
          >
            <code className="text-xs font-mono text-[var(--hud-text-secondary)] group-hover:text-[var(--hud-text-primary)]">
              {a.id}
            </code>
            <div className="flex items-center gap-3">
              <span
                className={[
                  'text-[0.6875rem] font-mono px-2 py-0.5 border',
                  a.label_status === 'labeled'
                    ? 'text-[var(--hud-success-text)] border-[var(--hud-success)]'
                    : 'text-[var(--hud-text-muted)] border-[var(--hud-border-default)]',
                ].join(' ')}
              >
                {a.label_status || 'unlabeled'}
              </span>
              <span className="text-xs font-mono text-[var(--hud-accent)] group-hover:underline">
                ANNOTATE →
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
