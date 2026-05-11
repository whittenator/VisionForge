import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Select from '@/components/ui/Select';
import Loading from '@/components/common/Loading';
import ClusterSelect from '@/components/common/ClusterSelect';
import { apiGet, apiPost } from '@/services/api';

interface Lineage {
  artifact?: {
    id: string;
    name?: string;
    type?: string;
    version?: number;
    runId?: string;
    createdAt?: string;
    storagePath?: string;
  };
  // Backwards-compat: pre-Phase 3 lineage shape was flat.
  id?: string;
  name?: string;
  type?: string;
  version?: number;
  run_id?: string;
  created_at?: string;
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
  const [clusterId, setClusterId]         = useState<string>('');
  const [dynamicAxes, setDynamicAxes]     = useState<boolean>(true);
  const [opset, setOpset]                 = useState<string>('');
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
      const body: Record<string, unknown> = { dynamic_axes: dynamicAxes };
      if (clusterId) body.cluster_id = clusterId;
      const opsetParsed = parseInt(opset, 10);
      if (Number.isFinite(opsetParsed) && opsetParsed > 0) body.opset = opsetParsed;
      const j = await apiPost<{ id: string; status: string }>(
        `/api/artifacts/models/${modelId}/export`,
        body,
      );
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
      {artifact && (() => {
        const a = artifact.artifact || artifact;
        const name = (a as any).name as string | undefined;
        const type = (a as any).type as string | undefined;
        const version = (a as any).version as number | undefined;
        const runId =
          ((a as any).runId as string | undefined) ||
          ((a as any).run_id as string | undefined);
        const createdAt =
          ((a as any).createdAt as string | undefined) ||
          ((a as any).created_at as string | undefined);
        return (
          <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
            <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
              <span className="label-overline">Model Info</span>
            </div>
            <table className="w-full text-xs font-mono">
              <tbody>
                {name && (
                  <tr className="border-b border-[var(--hud-border-subtle)]">
                    <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Name</td>
                    <td className="px-4 py-1.5 text-[var(--hud-text-primary)]">{name}</td>
                  </tr>
                )}
                {type && (
                  <tr className="border-b border-[var(--hud-border-subtle)]">
                    <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Type</td>
                    <td className="px-4 py-1.5"><Badge>{type}</Badge></td>
                  </tr>
                )}
                {version != null && (
                  <tr className="border-b border-[var(--hud-border-subtle)]">
                    <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Version</td>
                    <td className="px-4 py-1.5 text-[var(--hud-text-data)]">v{version}</td>
                  </tr>
                )}
                {runId && (
                  <tr className="border-b border-[var(--hud-border-subtle)]">
                    <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Training Run</td>
                    <td className="px-4 py-1.5">
                      <Link
                        to={`/experiments/runs/${runId}`}
                        className="text-[var(--hud-accent)] hover:underline underline-offset-1"
                      >
                        {runId.slice(0, 12)}…
                      </Link>
                    </td>
                  </tr>
                )}
                {createdAt && (
                  <tr>
                    <td className="px-4 py-1.5 text-[var(--hud-text-muted)] uppercase">Created</td>
                    <td className="px-4 py-1.5 text-[var(--hud-text-secondary)]">
                      {new Date(createdAt).toLocaleString()}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        );
      })()}

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
            <div className="space-y-3">
              <div>
                <label className="label-overline block mb-1" htmlFor="onnx-cluster">
                  Compute Cluster
                </label>
                <ClusterSelect
                  id="onnx-cluster"
                  kind="eval"
                  value={clusterId}
                  onChange={setClusterId}
                  allowAuto
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label-overline block mb-1" htmlFor="onnx-dynamic">
                    Dynamic Axes
                  </label>
                  <Select
                    id="onnx-dynamic"
                    value={dynamicAxes ? 'on' : 'off'}
                    onChange={(e) => setDynamicAxes(e.target.value === 'on')}
                  >
                    <option value="on">On (variable batch / size)</option>
                    <option value="off">Off (fixed shapes)</option>
                  </Select>
                </div>
                <div>
                  <label className="label-overline block mb-1" htmlFor="onnx-opset">
                    ONNX Opset
                  </label>
                  <Select
                    id="onnx-opset"
                    value={opset}
                    onChange={(e) => setOpset(e.target.value)}
                  >
                    <option value="">auto</option>
                    <option value="13">13</option>
                    <option value="14">14</option>
                    <option value="15">15</option>
                    <option value="16">16</option>
                    <option value="17">17</option>
                  </Select>
                </div>
              </div>
              <Button onClick={onExport} disabled={exporting || !modelId}>
                {exporting ? 'Starting export…' : 'Export to ONNX'}
              </Button>
            </div>
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
