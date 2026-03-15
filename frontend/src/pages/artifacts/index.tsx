import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface Artifact {
  id: string;
  type: string;
  version: number;
  name?: string;
  run_id?: string;
  project_id?: string;
  project_name?: string;
  file_size_bytes?: number;
  created_at: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function typeVariant(type: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (type?.toLowerCase()) {
    case 'onnx': return 'success';
    case 'pytorch': return 'warning';
    case 'weights': return 'default';
    default: return 'default';
  }
}

export default function ArtifactsIndex() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Artifact[]>('/api/artifacts/models')
      .then(setArtifacts)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load artifacts'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading artifacts…" />;
  if (error) return <ErrorState title="Failed to load artifacts" description={error} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Artifacts</h1>
        <Link to="/experiments" className="text-sm text-blue-600 hover:underline">
          View Training Runs
        </Link>
      </div>

      {artifacts.length === 0 ? (
        <EmptyState
          title="No model artifacts yet"
          description="Train a model to generate artifacts for export and deployment."
        >
          <Link
            to="/experiments/new"
            className="inline-flex items-center rounded-md bg-blue-600 text-white px-4 h-9 text-sm hover:bg-blue-700"
          >
            New Training Run
          </Link>
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {artifacts.map((a) => (
            <Card key={a.id} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">
                    {a.name || `Model v${a.version}`}
                  </CardTitle>
                  <Badge variant={typeVariant(a.type)}>{a.type}</Badge>
                </div>
              </CardHeader>
              <CardContent className="flex-1 space-y-2 text-sm">
                <div className="text-muted-foreground space-y-1">
                  {a.project_name && (
                    <div>Project: <span className="text-foreground">{a.project_name}</span></div>
                  )}
                  {a.run_id && (
                    <div>
                      Run:{' '}
                      <Link
                        to={`/experiments/runs/${a.run_id}`}
                        className="text-blue-600 hover:underline font-mono"
                      >
                        {a.run_id.slice(0, 8)}…
                      </Link>
                    </div>
                  )}
                  {a.file_size_bytes != null && (
                    <div>Size: <span className="text-foreground">{formatBytes(a.file_size_bytes)}</span></div>
                  )}
                  <div>Created: {new Date(a.created_at).toLocaleDateString()}</div>
                </div>

                <div className="flex gap-2 pt-2 border-t">
                  <Link
                    to={`/artifacts/export/${a.id}`}
                    className="inline-flex items-center rounded-md bg-blue-600 text-white px-3 h-8 text-xs hover:bg-blue-700"
                  >
                    Export ONNX
                  </Link>
                  <Link
                    to={`/artifacts/export/${a.id}`}
                    className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-8 text-xs hover:bg-gray-50"
                  >
                    View Lineage
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
