import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet, apiPost } from '@/services/api';

interface DuplicateAsset {
  id: string;
  uri: string;
  download_url: string;
}

interface DuplicatePair {
  distance: number;
  asset_a: DuplicateAsset;
  asset_b: DuplicateAsset;
}

interface DuplicatesResponse {
  pairs: DuplicatePair[];
  total: number;
  computed: boolean;
  truncated: boolean;
}

interface JobResponse {
  id: string;
  status: string;
  progress: number;
}

const THRESHOLDS = [
  { label: 'Exact', value: 0.01 },
  { label: 'Strict', value: 0.03 },
  { label: 'Normal', value: 0.05 },
  { label: 'Loose', value: 0.1 },
];

export default function DatasetDuplicates() {
  const { datasetId } = useParams<{ datasetId: string }>();

  const [threshold, setThreshold] = useState(0.05);
  const [data, setData] = useState<DuplicatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [datasetName, setDatasetName] = useState('');
  const [generating, setGenerating] = useState(false);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    apiGet<{ id: string; name: string }>(`/api/datasets/${datasetId}`)
      .then((d) => setDatasetName(d.name))
      .catch(console.error);
  }, [datasetId]);

  const refresh = useCallback(() => {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    apiGet<DuplicatesResponse>(
      `/api/datasets/${datasetId}/duplicates?threshold=${threshold}&limit=500`,
    )
      .then((res) => setData(res))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load duplicates'))
      .finally(() => setLoading(false));
  }, [datasetId, threshold]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function generateEmbeddings() {
    if (!datasetId) return;
    setGenerating(true);
    setError(null);
    setJobStatus('queued');
    try {
      const res = await apiPost<{ jobId: string; status: string }>(
        `/api/datasets/${datasetId}/embeddings`,
      );
      pollJob(res.jobId);
    } catch (err) {
      setGenerating(false);
      setJobStatus(null);
      setError(err instanceof Error ? err.message : 'Failed to queue embeddings');
    }
  }

  function pollJob(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const job = await apiGet<JobResponse>(`/api/jobs/${jobId}`);
        setJobStatus(job.status);
        if (['succeeded', 'failed', 'cancelled'].includes(job.status)) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setGenerating(false);
          if (job.status === 'succeeded') {
            refresh();
          } else {
            setError(`Embedding job ${job.status}`);
          }
        }
      } catch (err) {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        setGenerating(false);
        setError(err instanceof Error ? err.message : 'Failed to poll job');
      }
    }, 2000);
  }

  const pairs = data?.pairs ?? [];

  return (
    <div className="space-y-4">
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
          <span className="text-[var(--hud-text-secondary)]">DUPLICATES</span>
        </nav>
        <h1>Duplicate Detection</h1>
        <p className="text-xs text-[var(--hud-text-muted)] mt-1">
          Near-duplicate image pairs ranked by embedding cosine distance.
        </p>
      </div>

      {/* Controls */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3 flex flex-wrap items-end gap-3">
        <div>
          <label className="label-overline block mb-1" htmlFor="dup-threshold">
            Threshold
          </label>
          <div className="flex gap-1">
            {THRESHOLDS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setThreshold(t.value)}
                className={[
                  'px-2.5 py-1 text-xs font-mono border transition-colors',
                  threshold === t.value
                    ? 'border-[var(--hud-accent)] bg-[var(--hud-elevated)] text-[var(--hud-text-primary)]'
                    : 'border-[var(--hud-border-default)] text-[var(--hud-text-muted)] hover:bg-[var(--hud-elevated)]',
                ].join(' ')}
              >
                {t.label} ≤{t.value}
              </button>
            ))}
          </div>
        </div>

        <div className="ml-auto flex items-end gap-2">
          {data && (
            <span className="text-xs font-mono text-[var(--hud-text-muted)]">
              {data.total} pair{data.total === 1 ? '' : 's'}
              {data.truncated && ' (scan truncated)'}
            </span>
          )}
          <Button onClick={refresh} size="md" variant="ghost" disabled={loading}>
            Refresh
          </Button>
          <Button onClick={generateEmbeddings} size="md" disabled={generating}>
            {generating ? `Embedding… ${jobStatus ?? ''}` : 'Generate Embeddings'}
          </Button>
        </div>
      </div>

      {error && <ErrorState title="Duplicate detection error" description={error} />}

      {loading ? (
        <div className="py-6">
          <Loading label="Scanning for duplicates…" />
        </div>
      ) : data && !data.computed ? (
        <EmptyState
          title="No embeddings yet"
          description="Generate embeddings for this dataset to enable duplicate detection."
        >
          <Button onClick={generateEmbeddings} disabled={generating}>
            {generating ? `Embedding… ${jobStatus ?? ''}` : 'Generate embeddings'}
          </Button>
        </EmptyState>
      ) : pairs.length === 0 ? (
        <EmptyState
          title="No duplicates found"
          description="No asset pairs fall within the current distance threshold."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {pairs.map((pair) => (
            <div
              key={`${pair.asset_a.id}-${pair.asset_b.id}`}
              className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-2"
            >
              <div className="flex gap-2">
                {[pair.asset_a, pair.asset_b].map((asset) => (
                  <div key={asset.id} className="flex-1 min-w-0">
                    <div className="aspect-square bg-[var(--hud-elevated)] overflow-hidden border border-[var(--hud-border-subtle)]">
                      <img
                        src={asset.download_url}
                        alt={asset.id}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>
                    <div className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-1 truncate">
                      {asset.id.slice(0, 12)}…
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="label-overline">DISTANCE</span>
                <span className="text-xs font-mono text-[var(--hud-text-data)]">
                  {pair.distance.toFixed(4)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
