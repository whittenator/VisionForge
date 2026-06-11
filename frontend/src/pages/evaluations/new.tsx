import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import ClusterSelect from '@/components/common/ClusterSelect';
import { apiGet, apiPost } from '@/services/api';

interface ModelArtifact {
  id: string;
  name: string;
  version: string;
  type: string;
  format: string;
  projectId: string;
  runId?: string | null;
}

interface DatasetSummary {
  id: string;
  name: string;
  latest_version_id?: string | null;
}

export default function EvaluationsNew() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [models, setModels] = useState<ModelArtifact[]>([]);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [form, setForm] = useState({
    artifact_id: params.get('artifact_id') || '',
    dataset_version_id: params.get('dataset_version_id') || '',
    split: 'test',
    cluster_id: '',
    iou_threshold: 0.5,
    score_threshold: 0.25,
    sample_fpfn_count: 50,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiGet<{ items: ModelArtifact[] }>('/api/artifacts/models?page=1&page_size=200'),
      apiGet<{ items: DatasetSummary[] }>('/api/datasets?page=1&page_size=200'),
    ])
      .then(([m, d]) => {
        setModels(m.items || []);
        setDatasets(d.items || []);
      })
      .catch((err) =>
        setLoadError(err instanceof Error ? err.message : 'Failed to load models and datasets'),
      );
  }, []);

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // parseFloat with explicit NaN guard so 0 / 0.0 round-trip correctly
  // (`parseFloat(...) || fallback` is wrong because 0 is falsy).
  function safeFloat(raw: string, fallback: number): number {
    const parsed = parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  function safeInt(raw: string, fallback: number): number {
    const parsed = parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.artifact_id || !form.dataset_version_id) {
      setError('Pick a model and a dataset version');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const job = await apiPost<{ evaluationId: string; jobId: string; id: string }>(
        '/api/evaluations',
        {
          artifact_id: form.artifact_id,
          dataset_version_id: form.dataset_version_id,
          split: form.split,
          cluster_id: form.cluster_id || null,
          iou_threshold: form.iou_threshold,
          score_threshold: form.score_threshold,
          sample_fpfn_count: form.sample_fpfn_count,
        },
      );
      if (!job.evaluationId) {
        throw new Error('server response missing evaluationId');
      }
      navigate(`/evaluations/${job.evaluationId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start evaluation');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Evaluations / New</div>
          <h1>Evaluate a model</h1>
        </div>
        <Link
          to="/evaluations"
          className="text-xs font-mono text-[var(--hud-accent)] hover:underline"
        >
          ← EVALUATIONS
        </Link>
      </div>

      {loadError && <Alert variant="error">Failed to load models and datasets: {loadError}</Alert>}

      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="label-overline block mb-1">Model artifact</label>
          <Select
            value={form.artifact_id}
            onChange={(e) => setField('artifact_id', e.target.value)}
          >
            <option value="">— select —</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} v{m.version} ({m.format})
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="label-overline block mb-1">Dataset version</label>
          <Select
            value={form.dataset_version_id}
            onChange={(e) => setField('dataset_version_id', e.target.value)}
          >
            <option value="">— select —</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.latest_version_id || ''} disabled={!d.latest_version_id}>
                {d.name}
                {!d.latest_version_id ? ' (no versions yet)' : ''}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline block mb-1">IoU threshold</label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={form.iou_threshold}
              onChange={(e) => setField('iou_threshold', safeFloat(e.target.value, 0.5))}
            />
          </div>
          <div>
            <label className="label-overline block mb-1">Score threshold</label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={form.score_threshold}
              onChange={(e) => setField('score_threshold', safeFloat(e.target.value, 0.25))}
            />
          </div>
          <div>
            <label className="label-overline block mb-1">FP/FN sample budget</label>
            <Input
              type="number"
              min={0}
              max={500}
              value={form.sample_fpfn_count}
              onChange={(e) => setField('sample_fpfn_count', safeInt(e.target.value, 0))}
            />
          </div>
          <div>
            <label className="label-overline block mb-1">Split</label>
            <Select value={form.split} onChange={(e) => setField('split', e.target.value)}>
              <option value="test">test</option>
              <option value="val">val</option>
              <option value="all">all labeled</option>
            </Select>
          </div>
        </div>
        <div>
          <label className="label-overline block mb-1">Cluster</label>
          <ClusterSelect
            kind="eval"
            value={form.cluster_id}
            onChange={(v) => setField('cluster_id', v)}
            allowAuto
          />
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        <Button type="submit" disabled={loading}>
          {loading ? 'Starting…' : 'Start evaluation'}
        </Button>
      </form>
    </div>
  );
}
