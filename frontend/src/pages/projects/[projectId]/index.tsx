import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
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
    case 'succeeded': return 'success';
    case 'running':   return 'warning';
    case 'failed':    return 'danger';
    default:          return 'default';
  }
}

function StatCell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3">
      <div className="label-overline mb-1">{label}</div>
      <div className="text-xl font-semibold font-mono text-[var(--hud-text-data)]">{value}</div>
    </div>
  );
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

  if (loading) return <div className="py-6"><Loading label="Loading project…" /></div>;
  if (error) return <ErrorState title="Failed to load project" description={error} />;
  if (!project) return <ErrorState title="Project not found" />;

  return (
    <div className="space-y-5">
      {/* Breadcrumb + header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <nav className="label-overline mb-1">
          <Link to="/projects" className="hover:text-[var(--hud-accent)] transition-colors">PROJECTS</Link>
          <span className="mx-1.5 text-[var(--hud-border-strong)]">/</span>
          <span className="text-[var(--hud-text-secondary)]">{project.name.toUpperCase()}</span>
        </nav>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2">
              {project.name}
              <Badge variant={project.status === 'active' ? 'success' : 'default'}>
                {project.status || 'active'}
              </Badge>
            </h1>
            {project.description && (
              <p className="text-xs text-[var(--hud-text-muted)] mt-1 max-w-xl">{project.description}</p>
            )}
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <Button as="a" size="sm">
              <Link to={`/datasets/upload?projectId=${projectId}`}>Upload Assets</Link>
            </Button>
            <Button variant="outline" size="sm" as="a">
              <Link to={`/experiments/new?projectId=${projectId}`}>New Run</Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-[var(--hud-border-default)]">
        <StatCell label="Datasets" value={datasets.length} />
        <StatCell label="Total Assets" value={datasets.reduce((s, d) => s + (d.asset_count || 0), 0)} />
        <StatCell label="Training Runs" value={runs.length} />
        <StatCell
          label="Created"
          value={
            <span className="text-sm font-normal text-[var(--hud-text-secondary)]">
              {new Date(project.created_at).toLocaleDateString()}
            </span>
          }
        />
      </div>

      {/* Two-column content */}
      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        {/* Datasets */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <span className="label-overline">Datasets</span>
            <Link to={`/datasets?projectId=${projectId}`} className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2">
              VIEW ALL →
            </Link>
          </div>

          {datasets.length === 0 ? (
            <EmptyState
              title="No datasets"
              description="Upload images or annotations to get started."
            >
              <Button size="sm" as="a">
                <Link to={`/datasets/upload?projectId=${projectId}`}>Upload Dataset</Link>
              </Button>
            </EmptyState>
          ) : (
            <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
              {datasets.map((ds) => (
                <div key={ds.id} className="flex items-center justify-between px-3 py-2.5 hover:bg-[var(--hud-elevated)] transition-colors">
                  <div>
                    <div className="text-sm font-medium text-[var(--hud-text-primary)]">{ds.name}</div>
                    <div className="text-xs font-mono text-[var(--hud-text-muted)] mt-0.5">
                      {ds.asset_count} assets
                      {ds.latest_version != null && <span className="ml-2 text-[var(--hud-accent)]">v{ds.latest_version}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs font-mono">
                    <Link
                      to={`/datasets/upload?projectId=${projectId}&datasetId=${ds.id}${ds.latest_version_id ? `&versionId=${ds.latest_version_id}` : ''}`}
                      className="text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] transition-colors"
                    >
                      UPLOAD
                    </Link>
                    <Link
                      to={`/datasets/version?datasetId=${ds.id}`}
                      className="text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] transition-colors"
                    >
                      SNAPSHOT
                    </Link>
                    {ds.asset_count > 0 && (
                      <Link
                        to={`/datasets/${ds.id}/annotate`}
                        className="text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)] transition-colors"
                      >
                        ANNOTATE
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Runs */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <span className="label-overline">Recent Runs</span>
            <Link to="/experiments" className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2">
              VIEW ALL →
            </Link>
          </div>

          {runs.length === 0 ? (
            <EmptyState title="No training runs" description="Launch a training run to train a model.">
              <Button size="sm" as="a">
                <Link to={`/experiments/new?projectId=${projectId}`}>New Run</Link>
              </Button>
            </EmptyState>
          ) : (
            <div className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
              {runs.map((r) => (
                <div key={r.id} className="flex items-center justify-between px-3 py-2.5 hover:bg-[var(--hud-elevated)] transition-colors">
                  <div>
                    <div className="text-sm font-medium text-[var(--hud-text-primary)]">
                      {r.name || `Run ${r.id.slice(0, 8)}`}
                    </div>
                    <div className="text-xs font-mono text-[var(--hud-text-muted)] mt-0.5">
                      {new Date(r.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={statusBadgeVariant(r.status)}>{r.status}</Badge>
                    <Link
                      to={`/experiments/runs/${r.id}`}
                      className="text-xs font-mono text-[var(--hud-accent)] hover:underline underline-offset-2"
                    >
                      →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Quick actions */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3">
        <div className="label-overline mb-2">Quick Actions</div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" as="a">
            <Link to={`/datasets/upload?projectId=${projectId}`}>Upload Dataset</Link>
          </Button>
          <Button variant="outline" size="sm" as="a">
            <Link to={`/experiments/new?projectId=${projectId}`}>New Training Run</Link>
          </Button>
          <Button variant="outline" size="sm" as="a">
            <Link to="/artifacts">View Artifacts</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
