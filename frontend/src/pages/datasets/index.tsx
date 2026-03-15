import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface Dataset {
  id: string;
  name: string;
  asset_count: number;
  latest_version?: number;
  latest_version_id?: string;
  project_id?: string;
  project_name?: string;
  created_at: string;
}

export default function DatasetsIndex() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') || '';

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = projectId
      ? `/api/datasets?project_id=${projectId}`
      : '/api/datasets';
    apiGet<Dataset[]>(url)
      .then(setDatasets)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load datasets'))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <Loading label="Loading datasets…" />;
  if (error) return <ErrorState title="Failed to load datasets" description={error} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Datasets</h1>
          {projectId && (
            <p className="text-sm text-muted-foreground mt-0.5">
              Filtered by project.{' '}
              <Link to="/datasets" className="text-blue-600 hover:underline">Show all</Link>
            </p>
          )}
        </div>
        <Link
          to={projectId ? `/datasets/upload?projectId=${projectId}` : '/datasets/upload'}
          className="inline-flex items-center rounded-md bg-blue-600 text-white px-4 h-9 text-sm hover:bg-blue-700"
        >
          Upload Dataset
        </Link>
      </div>

      {datasets.length === 0 ? (
        <EmptyState
          title="No datasets yet"
          description="Upload images or annotation files to create a dataset."
        >
          <Link
            to="/datasets/upload"
            className="inline-flex items-center rounded-md bg-blue-600 text-white px-4 h-9 text-sm hover:bg-blue-700"
          >
            Upload Dataset
          </Link>
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((ds) => (
            <Card key={ds.id} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{ds.name}</CardTitle>
                  {ds.latest_version != null && (
                    <Badge variant="default">v{ds.latest_version}</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex-1 space-y-3 text-sm">
                <div className="text-muted-foreground space-y-1">
                  <div>
                    Assets:{' '}
                    <span className="text-foreground font-medium">{ds.asset_count}</span>
                  </div>
                  {ds.project_name && (
                    <div>
                      Project:{' '}
                      <span className="text-foreground">{ds.project_name}</span>
                    </div>
                  )}
                  <div>Created: {new Date(ds.created_at).toLocaleDateString()}</div>
                </div>

                <div className="flex flex-wrap gap-2 pt-2 border-t">
                  <Link
                    to={`/datasets/upload?datasetId=${ds.id}${ds.latest_version_id ? `&versionId=${ds.latest_version_id}` : ''}${ds.project_id ? `&projectId=${ds.project_id}` : ''}`}
                    className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-7 text-xs hover:bg-gray-50"
                  >
                    Upload Assets
                  </Link>
                  <Link
                    to={`/datasets/version?datasetId=${ds.id}`}
                    className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-7 text-xs hover:bg-gray-50"
                  >
                    Create Snapshot
                  </Link>
                  {ds.asset_count > 0 && (
                    <Link
                      to={`/annotate/${ds.id}`}
                      className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-7 text-xs hover:bg-gray-50"
                    >
                      Annotate
                    </Link>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
