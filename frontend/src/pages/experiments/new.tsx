import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiPost } from '@/services/api';

interface Project {
  id: string;
  name: string;
}

interface Dataset {
  id: string;
  name: string;
  latest_version_id?: string;
}

const BASE_MODELS = [
  'yolov8n.pt',
  'yolov8s.pt',
  'yolov8m.pt',
  'yolov8l.pt',
  'yolov8x.pt',
];

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
    apiGet<Project[]>('/api/projects')
      .then(setProjects)
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!form.projectId) {
      setDatasets([]);
      return;
    }
    apiGet<Dataset[]>(`/api/datasets?project_id=${form.projectId}`)
      .then(setDatasets)
      .catch(console.error);
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
        params: {
          epochs: form.epochs,
          batch: form.batchSize,
          imgsz: form.imageSize,
          lr0: form.learningRate,
          device: form.device,
        },
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
      <div className="max-w-lg mx-auto mt-12 text-center space-y-4">
        <div className="text-5xl">🚀</div>
        <h2 className="text-xl font-semibold">Training run launched!</h2>
        <p className="text-sm text-muted-foreground">
          Job ID: <code className="font-mono">{jobId}</code>
        </p>
        <p className="text-sm text-muted-foreground">Redirecting to experiments…</p>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">New Training Run</h1>
        <Link to="/experiments" className="text-sm text-blue-600 hover:underline">
          Back to Experiments
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            {/* Name */}
            <div className="space-y-1">
              <label htmlFor="run-name" className="block text-sm font-medium">Run Name</label>
              <Input
                id="run-name"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                placeholder="Baseline"
              />
            </div>

            {/* Project */}
            <div className="space-y-1">
              <label htmlFor="project-select" className="block text-sm font-medium">Project</label>
              <Select
                id="project-select"
                value={form.projectId}
                onChange={(e) => {
                  setField('projectId', e.target.value);
                  setField('datasetVersionId', '');
                }}
              >
                <option value="">— Select project —</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </Select>
            </div>

            {/* Dataset/Version */}
            <div className="space-y-1">
              <label htmlFor="dataset-select" className="block text-sm font-medium">Dataset Version</label>
              <Select
                id="dataset-select"
                value={form.datasetVersionId}
                onChange={(e) => setField('datasetVersionId', e.target.value)}
                disabled={!form.projectId || datasets.length === 0}
              >
                <option value="">— Select dataset —</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.latest_version_id || d.id}>
                    {d.name}
                    {d.latest_version_id ? '' : ' (no versions)'}
                  </option>
                ))}
              </Select>
              {form.projectId && datasets.length === 0 && (
                <p className="text-xs text-muted-foreground">No datasets found for this project.</p>
              )}
            </div>

            {/* Task */}
            <div className="space-y-1">
              <label htmlFor="task-select" className="block text-sm font-medium">Task</label>
              <Select
                id="task-select"
                value={form.task}
                onChange={(e) => setField('task', e.target.value)}
              >
                <option value="detect">Object Detection</option>
                <option value="classify">Classification</option>
                <option value="segment">Segmentation</option>
                <option value="pose">Pose Estimation</option>
              </Select>
            </div>

            {/* Base Model */}
            <div className="space-y-1">
              <label htmlFor="base-model" className="block text-sm font-medium">Base Model</label>
              <Select
                id="base-model"
                value={form.baseModel}
                onChange={(e) => setField('baseModel', e.target.value)}
              >
                {BASE_MODELS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </Select>
            </div>

            {/* Hyperparameters */}
            <div className="rounded-lg border p-4 space-y-3">
              <h3 className="text-sm font-medium">Hyperparameters</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label htmlFor="epochs" className="block text-xs text-muted-foreground">Epochs</label>
                  <Input
                    id="epochs"
                    type="number"
                    min={1}
                    max={1000}
                    value={form.epochs}
                    onChange={(e) => setField('epochs', parseInt(e.target.value) || 1)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="batch-size" className="block text-xs text-muted-foreground">Batch Size</label>
                  <Input
                    id="batch-size"
                    type="number"
                    min={1}
                    max={512}
                    value={form.batchSize}
                    onChange={(e) => setField('batchSize', parseInt(e.target.value) || 1)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="image-size" className="block text-xs text-muted-foreground">Image Size</label>
                  <Input
                    id="image-size"
                    type="number"
                    min={32}
                    max={1280}
                    step={32}
                    value={form.imageSize}
                    onChange={(e) => setField('imageSize', parseInt(e.target.value) || 640)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="lr" className="block text-xs text-muted-foreground">Learning Rate</label>
                  <Input
                    id="lr"
                    type="number"
                    min={0.00001}
                    max={1}
                    step={0.0001}
                    value={form.learningRate}
                    onChange={(e) => setField('learningRate', parseFloat(e.target.value) || 0.001)}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label htmlFor="device" className="block text-xs text-muted-foreground">Device</label>
                <Select
                  id="device"
                  value={form.device}
                  onChange={(e) => setField('device', e.target.value)}
                >
                  <option value="cpu">CPU</option>
                  <option value="cuda">CUDA (GPU)</option>
                  <option value="mps">MPS (Apple Silicon)</option>
                  <option value="0">GPU:0</option>
                  <option value="0,1">GPU:0,1</option>
                </Select>
              </div>
            </div>

            {error && <Alert variant="error">{error}</Alert>}

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? (
                <span className="flex items-center gap-2">
                  <Spinner />
                  Launching…
                </span>
              ) : (
                'Launch Training Run'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
