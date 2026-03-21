import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
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
    case 'running': return 'warning';
    case 'failed': return 'danger';
    default: return 'default';
  }
}

export default function ArtifactsExport() {
  const { modelId } = useParams<{ modelId: string }>();
  const [artifact, setArtifact] = useState<Lineage | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(true);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!modelId) return;
    apiGet<Lineage>(`/api/artifacts/models/${modelId}/lineage`)
      .then(setArtifact)
      .catch((err) => setArtifactError(err instanceof Error ? err.message : 'Failed to load artifact'))
      .finally(() => setArtifactLoading(false));
  }, [modelId]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
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
          if (updated.status === 'succeeded' && modelId) {
            apiGet<{ url: string; filename: string }>(`/api/artifacts/models/${modelId}/download`)
              .then(data => setDownloadUrl(data.url))
              .catch(() => {});
          }
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
      const j = await apiPost<{ id: string; status: string }>(
        `/api/artifacts/models/${modelId}/export`,
        {}
      );
      const initial: JobStatus = { id: j.id, status: j.status, progress: 0 };
      setJob(initial);
      pollJob(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
      setExporting(false);
    }
  }

  if (artifactLoading) return <Loading label="Loading model info…" />;

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Export to ONNX</h1>
        <Link to="/artifacts" className="text-sm text-blue-600 hover:underline">
          Back to Artifacts
        </Link>
      </div>

      {artifactError && (
        <Alert variant="warning">Could not load model lineage: {artifactError}</Alert>
      )}

      {/* Model lineage info */}
      {artifact && (
        <Card>
          <CardHeader>
            <CardTitle>Model Info</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <tbody>
                {artifact.name && (
                  <tr className="border-b">
                    <td className="py-1.5 pr-4 text-muted-foreground">Name</td>
                    <td className="py-1.5 font-medium">{artifact.name}</td>
                  </tr>
                )}
                {artifact.type && (
                  <tr className="border-b">
                    <td className="py-1.5 pr-4 text-muted-foreground">Type</td>
                    <td className="py-1.5">
                      <Badge>{artifact.type}</Badge>
                    </td>
                  </tr>
                )}
                {artifact.version != null && (
                  <tr className="border-b">
                    <td className="py-1.5 pr-4 text-muted-foreground">Version</td>
                    <td className="py-1.5">v{artifact.version}</td>
                  </tr>
                )}
                {artifact.run_id && (
                  <tr className="border-b">
                    <td className="py-1.5 pr-4 text-muted-foreground">Training Run</td>
                    <td className="py-1.5">
                      <Link
                        to={`/experiments/runs/${artifact.run_id}`}
                        className="text-blue-600 hover:underline font-mono text-xs"
                      >
                        {artifact.run_id.slice(0, 12)}…
                      </Link>
                    </td>
                  </tr>
                )}
                {artifact.created_at && (
                  <tr>
                    <td className="py-1.5 pr-4 text-muted-foreground">Created</td>
                    <td className="py-1.5">{new Date(artifact.created_at).toLocaleString()}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Export controls */}
      <Card>
        <CardHeader><CardTitle>ONNX Export</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Export this model to ONNX format for inference with ONNXRuntime, OpenVINO, or other
            compatible frameworks.
          </p>

          {error && <Alert variant="error">{error}</Alert>}

          {!job && (
            <Button onClick={onExport} disabled={exporting || !modelId}>
              {exporting ? 'Starting export…' : 'Export to ONNX'}
            </Button>
          )}

          {job && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span>Export job</span>
                <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
              </div>
              <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                <div
                  style={{ width: `${job.progress}%` }}
                  className={`h-full rounded-full transition-all ${
                    job.status === 'failed' ? 'bg-red-500' : 'bg-blue-600'
                  }`}
                />
              </div>
              <p className="text-xs text-muted-foreground font-mono">{job.id}</p>

              {job.status === 'failed' && job.error_message && (
                <Alert variant="error">{job.error_message}</Alert>
              )}

              {job.status === 'succeeded' && (
                <div className="space-y-2">
                  <Alert variant="success">
                    Export complete! The ONNX model is stored in object storage.
                  </Alert>
                  {(downloadUrl || job.result_url) && (
                    <a
                      href={downloadUrl || job.result_url || ''}
                      className="inline-flex items-center gap-2 rounded-md bg-green-600 text-white px-4 h-9 text-sm hover:bg-green-700 transition-colors"
                      download
                    >
                      ⬇ Download .onnx
                    </a>
                  )}
                </div>
              )}

              {(job.status === 'failed' || job.status === 'succeeded') && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setJob(null);
                    setExporting(false);
                  }}
                >
                  Export Again
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
