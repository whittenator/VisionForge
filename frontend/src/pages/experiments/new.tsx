import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiPost } from '@/services/api';

interface Project { id: string; name: string; }
interface Dataset { id: string; name: string; latest_version_id?: string; }

const BASE_MODELS = ['yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt'];

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="label-overline block mb-1">
      {children}
    </label>
  );
}

export default function ExperimentsNew() {
  const [searchParams] = useSearchParams();
  const preselectedProject = searchParams.get('projectId') || '';

  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [form, setForm] = useState({
    projectId: preselectedProject,
    datasetVersionId: '',
    name: 'Baseline',
    task: 'detect',
    baseModel: 'yolov8n.pt',
    epochs: 50,
    batchSize: 16,
    imageSize: 640,
    learningRate: 0.001,
    device: 'cpu',
  });
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiGet<Project[]>('/api/projects').then(setProjects).catch(console.error);
  }, []);

  useEffect(() => {
    if (!form.projectId) { setDatasets([]); return; }
    apiGet<Dataset[]>(`/api/datasets?project_id=${form.projectId}`).then(setDatasets).catch(console.error);
  }, [form.projectId]);

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.projectId) { setError('Select a project'); return; }
    if (!form.datasetVersionId) { setError('Select a dataset/version'); return; }
    setLoading(true);
    setError(null);
    try {
      const job = await apiPost<{ id: string; status: string }>('/api/train', {
        projectId: form.projectId,
        datasetVersionId: form.datasetVersionId,
        task: form.task,
        baseModel: form.baseModel,
        name: form.name,
        params: { epochs: form.epochs, batch: form.batchSize, imgsz: form.imageSize, lr0: form.learningRate, device: form.device },
      });
      setJobId(job.id);
      setTimeout(() => navigate('/experiments'), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to launch training');
    } finally {
      setLoading(false);
    }
  }

  if (jobId) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center space-y-3">
        <div className="text-[var(--hud-success-text)] text-4xl font-mono">▲</div>
        <h2 className="text-base font-semibold tracking-wide text-[var(--hud-text-primary)]">
          Training run launched
        </h2>
        <div className="text-xs font-mono text-[var(--hud-text-muted)]">
          JOB_ID <span className="text-[var(--hud-text-data)]">{jobId}</span>
        </div>
        <p className="text-xs text-[var(--hud-text-muted)]">Redirecting to experiments…</p>
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Experiments / New</div>
          <h1>New Training Run</h1>
        </div>
        <Link to="/experiments" className="text-xs font-mono text-[var(--hud-accent)] hover:underline">
          ← EXPERIMENTS
        </Link>
      </div>

      {/* Form */}
      <form onSubmit={onSubmit} className="space-y-0">
        {/* Run config */}
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="label-overline">Run Configuration</span>
          </div>
          <div className="p-4 space-y-3">
            <div>
              <FieldLabel htmlFor="run-name">Run Name</FieldLabel>
              <Input id="run-name" value={form.name} onChange={(e) => setField('name', e.target.value)} placeholder="Baseline" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="project-select">Project</FieldLabel>
                <Select id="project-select" value={form.projectId} onChange={(e) => { setField('projectId', e.target.value); setField('datasetVersionId', ''); }}>
                  <option value="">— select —</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="dataset-select">Dataset Version</FieldLabel>
                <Select id="dataset-select" value={form.datasetVersionId} onChange={(e) => setField('datasetVersionId', e.target.value)} disabled={!form.projectId || datasets.length === 0}>
                  <option value="">— select —</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.latest_version_id || d.id}>
                      {d.name}{!d.latest_version_id ? ' (no versions)' : ''}
                    </option>
                  ))}
                </Select>
                {form.projectId && datasets.length === 0 && (
                  <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] mt-1">No datasets found</p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="task-select">Task</FieldLabel>
                <Select id="task-select" value={form.task} onChange={(e) => setField('task', e.target.value)}>
                  <option value="detect">Object Detection</option>
                  <option value="classify">Classification</option>
                  <option value="segment">Segmentation</option>
                  <option value="pose">Pose Estimation</option>
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="base-model">Base Model</FieldLabel>
                <Select id="base-model" value={form.baseModel} onChange={(e) => setField('baseModel', e.target.value)}>
                  {BASE_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                </Select>
              </div>
            </div>
          </div>
        </div>

        {/* Hyperparameters */}
        <div className="border border-t-0 border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
            <span className="label-overline">Hyperparameters</span>
          </div>
          <div className="p-4 grid grid-cols-2 gap-3">
            <div>
              <FieldLabel htmlFor="epochs">Epochs</FieldLabel>
              <Input id="epochs" type="number" min={1} max={1000} value={form.epochs} onChange={(e) => setField('epochs', parseInt(e.target.value) || 1)} />
            </div>
            <div>
              <FieldLabel htmlFor="batch-size">Batch Size</FieldLabel>
              <Input id="batch-size" type="number" min={1} max={512} value={form.batchSize} onChange={(e) => setField('batchSize', parseInt(e.target.value) || 1)} />
            </div>
            <div>
              <FieldLabel htmlFor="image-size">Image Size</FieldLabel>
              <Input id="image-size" type="number" min={32} max={1280} step={32} value={form.imageSize} onChange={(e) => setField('imageSize', parseInt(e.target.value) || 640)} />
            </div>
            <div>
              <FieldLabel htmlFor="lr">Learning Rate</FieldLabel>
              <Input id="lr" type="number" min={0.00001} max={1} step={0.0001} value={form.learningRate} onChange={(e) => setField('learningRate', parseFloat(e.target.value) || 0.001)} />
            </div>
            <div className="col-span-2">
              <FieldLabel htmlFor="device">Device</FieldLabel>
              <Select id="device" value={form.device} onChange={(e) => setField('device', e.target.value)}>
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA (GPU)</option>
                <option value="mps">MPS (Apple Silicon)</option>
                <option value="0">GPU:0</option>
                <option value="0,1">GPU:0,1</option>
              </Select>
            </div>
          </div>
        </div>

        {error && <Alert variant="error" className="mt-3">{error}</Alert>}

        <div className="pt-3">
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner size={12} />
                Launching…
              </span>
            ) : (
              'Launch Training Run'
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
