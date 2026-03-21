import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Loading from '@/components/common/Loading';
import ErrorState from '@/components/common/ErrorState';
import { apiGet, apiPost } from '@/services/api';

interface Lineage {
  id: string;
  name?: string;
  type?: string;
  version?: number;
  run_id?: string;
  project_id?: string;
  created_at?: string;
  storage_path?: string;
}

interface JobStatus {
  id: string;
  status: string;
  progress: number;
  error_message?: string;
  result_url?: string;
}

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'succeeded': return 'success';
    case 'running':   return 'warning';
    case 'failed':    return 'danger';
    default:          return 'default';
  }
}

export default function ArtifactsExport() {
  const { modelId } = useParams<{ modelId: string }>();
  const [artifact, setArtifact]           = useState<Lineage | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(true);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [job, setJob]                     = useState<JobStatus | null>(null);
  const [exporting, setExporting]         = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!modelId) return;
    apiGet<Lineage>(`/api/artifacts/models/${modelId}/lineage`)
      .then(setArtifact)
      .catch((err) => setArtifactError(err instanceof Error ? err.message : 'Failed to load artifact'))
      .finally(() => setArtifactLoading(false));
  }, [modelId]);

  useEffect(() => {
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  async function pollJob(jobId: string) {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      try {
        const updated = await apiGet<JobStatus>(`/api/jobs/${jobId}`);
        setJob(updated);
        if (updated.status === 'succeeded' || updated.status === 'failed') {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setExporting(false);
        }
      } catch (err) {
        console.error('Failed to poll job', err);
      }
    }, 2000);
  }

  async function onExport() {
    if (!modelId) return;
    setExporting(true);
    setError(null);
    try {
      const j = await apiPost<{ id: string; status: string }>(`/api/artifacts/models/${modelId}/export`, {});
      const initial: JobStatus = { id: j.id, status: j.status, progress: 0 };
      setJob(initial);
      pollJob(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
      setExporting(false);
    }
  }

  if (artifactLoading) return <div className="py-6"><Loading label="Loading model info…" /></div>;

  return (
    <div className="max-w-lg space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Artifacts / Export</div>
          <h1>Export to ONNX</h1>
        </div>
        <Link to="/artifacts" className="text-xs font-mono text-[var(--hud-accent)] hover:underline">
          ← ARTIFACTS
        </Link>
      </div>

      {artifactError && <Alert variant="warning">Could not load model lineage: {artifactError}</Alert>}

      {/* Model info */}
      {artifact && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
            <span className="label-overline">Model Info</span>
          </div>
          <table className="w-full text-xs font-mono">
            <tbody>
              {artifact.name && (
                <tr className="border-b border-[var(--hud-border-subtle)]">
                  <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Name</td>
                  <td className="px-4 py-1.5 text-[var(--hud-text-primary)]">{artifact.name}</td>
                </tr>
              )}
              {artifact.type && (
                <tr className="border-b border-[var(--hud-border-subtle)]">
                  <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Type</td>
                  <td className="px-4 py-1.5"><Badge>{artifact.type}</Badge></td>
                </tr>
              )}
              {artifact.version != null && (
                <tr className="border-b border-[var(--hud-border-subtle)]">
                  <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Version</td>
                  <td className="px-4 py-1.5 text-[var(--hud-text-data)]">v{artifact.version}</td>
                </tr>
              )}
              {artifact.run_id && (
                <tr className="border-b border-[var(--hud-border-subtle)]">
                  <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Training Run</td>
                  <td className="px-4 py-1.5">
                    <Link
                      to={`/experiments/runs/${artifact.run_id}`}
                      className="text-[var(--hud-accent)] hover:underline underline-offset-1"
                    >
                      {artifact.run_id.slice(0, 12)}…
                    </Link>
                  </td>
                </tr>
              )}
              {artifact.created_at && (
                <tr>
                  <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Created</td>
                  <td className="px-4 py-1.5 text-[var(--hud-text-secondary)]">
                    {new Date(artifact.created_at).toLocaleString()}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Export controls */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
        <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
          <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
          <span className="label-overline">ONNX Export</span>
        </div>
        <div className="p-4 space-y-4">
          <p className="text-xs text-[var(--hud-text-muted)]">
            Export this model to ONNX format for inference with ONNXRuntime, OpenVINO, or other compatible frameworks.
          </p>

          {error && <Alert variant="error">{error}</Alert>}

          {!job && (
            <Button onClick={onExport} disabled={exporting || !modelId}>
              {exporting ? 'Starting export…' : 'Export to ONNX'}
            </Button>
          )}

          {job && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-[var(--hud-text-muted)]">EXPORT JOB</span>
                <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
              </div>

              {/* Progress bar */}
              <div className="h-1 w-full bg-[var(--hud-inset)] overflow-hidden">
                <div
                  style={{ width: `${job.progress}%` }}
                  className={`h-full transition-all ${job.status === 'failed' ? 'bg-[var(--hud-danger)]' : 'bg-[var(--hud-accent)]'}`}
                />
              </div>

              <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">{job.id}</p>

              {job.status === 'failed' && job.error_message && (
                <Alert variant="error">{job.error_message}</Alert>
              )}

              {job.status === 'succeeded' && (
                <div className="space-y-2">
                  <Alert variant="success">Export complete — ONNX model stored in object storage.</Alert>
                  {job.result_url && (
                    <a
                      href={job.result_url}
                      className="inline-flex items-center h-8 px-3 text-xs font-mono font-medium bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border border-[var(--hud-accent)] hover:bg-[var(--hud-accent-hover)] transition-colors"
                      download
                    >
                      DOWNLOAD ONNX MODEL
                    </a>
                  )}
                </div>
              )}

              {(job.status === 'failed' || job.status === 'succeeded') && (
                <Button variant="outline" size="sm" onClick={() => { setJob(null); setExporting(false); }}>
                  Export Again
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
