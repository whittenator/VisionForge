import React, { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiPost } from '@/services/api';

interface SnapshotResult {
  id: string;
  version: number;
  asset_count: number;
}

export default function DatasetVersion() {
  const [searchParams] = useSearchParams();
  const datasetId = searchParams.get('datasetId') || '';
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SnapshotResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function onSnapshot() {
    if (!datasetId) {
      setError('No dataset selected. Pass ?datasetId=... in the URL.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const v = await apiPost<SnapshotResult>(`/api/datasets/${datasetId}/snapshot`, { notes });
      setResult(v);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create snapshot');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <div className="label-overline mb-0.5">// Datasets / Snapshot</div>
        <h1>Create Dataset Snapshot</h1>
      </div>

      {!datasetId && (
        <Alert variant="warning">
          No dataset selected. Pass <code className="font-mono">?datasetId=...</code> in the URL.
        </Alert>
      )}

      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
        <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="label-overline">New Version</span>
          </div>
          {datasetId && (
            <span className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
              {datasetId.slice(0, 12)}…
            </span>
          )}
        </div>

        <div className="p-4 space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="notes" className="label-overline block">
              Release Notes <span className="text-[var(--hud-text-muted)]">(optional)</span>
            </label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              placeholder="Describe changes in this version…"
              className="w-full border border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-3 py-2 text-sm text-[var(--hud-text-primary)] placeholder:text-[var(--hud-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--hud-accent)] focus:border-[var(--hud-border-accent)] resize-none transition-colors font-mono"
            />
          </div>

          {error && <Alert variant="error">{error}</Alert>}

          {result && (
            <Alert variant="success">
              Snapshot created: <strong className="font-mono">v{result.version}</strong> · {result.asset_count} asset(s)
            </Alert>
          )}

          <div className="flex items-center gap-2">
            <Button onClick={onSnapshot} disabled={loading || !datasetId}>
              {loading ? (
                <span className="flex items-center gap-2">
                  <Spinner size={12} />
                  Creating…
                </span>
              ) : (
                'Create Snapshot'
              )}
            </Button>
            {result && (
              <Button
                variant="outline"
                onClick={() => navigate(`/datasets/upload?datasetId=${datasetId}&versionId=${result.id}`)}
              >
                Upload to v{result.version}
              </Button>
            )}
          </div>

          {result && (
            <div className="pt-3 border-t border-[var(--hud-border-subtle)] space-y-1 text-xs font-mono">
              <div>
                <span className="text-[var(--hud-text-muted)]">VERSION ID </span>
                <span className="text-[var(--hud-text-data)]">{result.id}</span>
              </div>
              <Link
                to={`/datasets?datasetId=${datasetId}`}
                className="text-[var(--hud-accent)] hover:underline underline-offset-2"
              >
                View all versions →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
