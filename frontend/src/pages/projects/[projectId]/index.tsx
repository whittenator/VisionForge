import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import EmptyState from '@/components/common/EmptyState';
import { apiGet } from '@/services/api';

interface ProjectDetail {
  id: string;
  name: string;
  description?: string;
  workspace_id: string;
  status: string;
  dataset_count: number;
  created_at: string;
}

interface Dataset {
  id: string;
  name: string;
  asset_count: number;
  latest_version?: number;
  latest_version_id?: string;
}

interface Run {
  id: string;
  name: string;
  status: string;
  project_id?: string;
  created_at: string;
}

function statusBadgeVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'succeeded':
      return 'success';
    case 'running':
      return 'warning';
    case 'failed':
      return 'danger';
    default:
      return 'default';
  }
}

export default function ProjectDashboard() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      apiGet<ProjectDetail>(`/api/projects/${projectId}`),
      apiGet<Dataset[]>(`/api/projects/${projectId}/datasets`),
      apiGet<Run[]>('/api/experiments/runs'),
    ])
      .then(([proj, ds, allRuns]) => {
        setProject(proj);
        setDatasets(ds);
        setRuns(allRuns.filter((r) => r.project_id === projectId).slice(0, 5));
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load project'))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <Loading label="Loading project…" />;
  if (error) return <ErrorState title="Failed to load project" description={error} />;
  if (!project) return <ErrorState title="Project not found" />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <nav className="text-xs text-muted-foreground mb-1">
            <Link to="/projects" className="hover:underline">Projects</Link>
            {' / '}
            <span>{project.name}</span>
          </nav>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          {project.description && (
            <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <Link
            to={`/datasets/upload?projectId=${projectId}`}
            className="inline-flex items-center rounded-md bg-blue-600 text-white px-4 h-9 text-sm hover:bg-blue-700"
          >
            Upload Assets
          </Link>
          <Link
            to={`/experiments/new?projectId=${projectId}`}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 h-9 text-sm hover:bg-gray-50"
          >
            New Training Run
          </Link>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-lg border bg-card p-4">
          <div className="text-sm text-muted-foreground">Datasets</div>
          <div className="text-2xl font-semibold mt-1">{datasets.length}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="text-sm text-muted-foreground">Total Assets</div>
          <div className="text-2xl font-semibold mt-1">
            {datasets.reduce((sum, d) => sum + (d.asset_count || 0), 0)}
          </div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="text-sm text-muted-foreground">Training Runs</div>
          <div className="text-2xl font-semibold mt-1">{runs.length}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="text-sm text-muted-foreground">Status</div>
          <div className="mt-1">
            <Badge>{project.status || 'active'}</Badge>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* Datasets section */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium">Datasets</h2>
            <Link
              to={`/datasets?projectId=${projectId}`}
              className="text-sm text-blue-600 hover:underline"
            >
              View all
            </Link>
          </div>

          {datasets.length === 0 ? (
            <EmptyState
              title="No datasets yet"
              description="Upload images or annotations to get started."
            >
              <Link
                to={`/datasets/upload?projectId=${projectId}`}
                className="inline-flex items-center rounded-md bg-blue-600 text-white px-4 h-9 text-sm hover:bg-blue-700"
              >
                Upload Dataset
              </Link>
            </EmptyState>
          ) : (
            <div className="space-y-3">
              {datasets.map((ds) => (
                <Card key={ds.id}>
                  <CardContent className="py-3 flex items-center justify-between">
                    <div>
                      <div className="font-medium text-sm">{ds.name}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {ds.asset_count} asset(s)
                        {ds.latest_version != null && ` · v${ds.latest_version}`}
                      </div>
                    </div>
                    <div className="flex gap-2 text-sm">
                      <Link
                        to={`/datasets/upload?projectId=${projectId}&datasetId=${ds.id}${ds.latest_version_id ? `&versionId=${ds.latest_version_id}` : ''}`}
                        className="text-blue-600 hover:underline"
                      >
                        Upload
                      </Link>
                      <Link
                        to={`/datasets/version?datasetId=${ds.id}`}
                        className="text-blue-600 hover:underline"
                      >
                        Snapshot
                      </Link>
                      {ds.asset_count > 0 && (
                        <Link
                          to={`/annotate/${ds.id}`}
                          className="text-blue-600 hover:underline"
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
        </section>

        {/* Recent Runs */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium">Recent Training Runs</h2>
            <Link to="/experiments" className="text-sm text-blue-600 hover:underline">
              View all
            </Link>
          </div>

          {runs.length === 0 ? (
            <EmptyState
              title="No training runs yet"
              description="Launch a new training run to train a model."
            >
              <Link
                to={`/experiments/new?projectId=${projectId}`}
                className="inline-flex items-center rounded-md bg-blue-600 text-white px-4 h-9 text-sm hover:bg-blue-700"
              >
                New Run
              </Link>
            </EmptyState>
          ) : (
            <div className="space-y-2">
              {runs.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded-lg border bg-card px-4 py-2.5"
                >
                  <div>
                    <div className="text-sm font-medium">{r.name || `Run ${r.id.slice(0, 8)}`}</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={statusBadgeVariant(r.status)}>{r.status}</Badge>
                    <Link
                      to={`/experiments/runs/${r.id}`}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Details
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Quick actions */}
      <section className="rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Quick Actions</h2>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/datasets/upload?projectId=${projectId}`}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-8 text-sm hover:bg-gray-50"
          >
            Upload Dataset
          </Link>
          <Link
            to={`/experiments/new?projectId=${projectId}`}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-8 text-sm hover:bg-gray-50"
          >
            New Training Run
          </Link>
          <Link
            to="/artifacts"
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 h-8 text-sm hover:bg-gray-50"
          >
            View Artifacts
          </Link>
        </div>
      </section>

      <div className="text-xs text-muted-foreground">
        Created {new Date(project.created_at).toLocaleDateString()}
      </div>
    </div>
  );
}
