import React, { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
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
      const v = await apiPost<SnapshotResult>(
        `/api/datasets/${datasetId}/snapshot`,
        { notes }
      );
      setResult(v);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create snapshot');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <h1 className="text-2xl font-semibold">Create Dataset Snapshot</h1>

      {!datasetId && (
        <Alert variant="warning">
          No dataset selected. Pass <code>?datasetId=...</code> in the URL.
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>New Version</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {datasetId && (
            <p className="text-sm text-muted-foreground">
              Dataset: <code className="font-mono">{datasetId}</code>
            </p>
          )}

          <div className="space-y-1">
            <label htmlFor="notes" className="block text-sm font-medium">
              Release Notes <span className="text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              placeholder="Describe what changed in this version…"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && (
            <Alert variant="error">{error}</Alert>
          )}

          {result && (
            <Alert variant="success">
              Snapshot created: <strong>v{result.version}</strong> with{' '}
              <strong>{result.asset_count}</strong> asset(s).
            </Alert>
          )}

          <div className="flex items-center gap-3">
            <Button onClick={onSnapshot} disabled={loading || !datasetId}>
              {loading ? (
                <span className="flex items-center gap-2">
                  <Spinner />
                  Creating…
                </span>
              ) : (
                'Create Snapshot'
              )}
            </Button>

            {result && (
              <Button
                variant="outline"
                onClick={() =>
                  navigate(
                    `/datasets/upload?datasetId=${datasetId}&versionId=${result.id}`
                  )
                }
              >
                Upload to v{result.version}
              </Button>
            )}
          </div>

          {result && (
            <div className="pt-2 border-t text-sm space-y-1">
              <p className="text-muted-foreground">Version ID: <code className="font-mono">{result.id}</code></p>
              <Link
                to={`/datasets?datasetId=${datasetId}`}
                className="text-blue-600 hover:underline"
              >
                View all versions
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
