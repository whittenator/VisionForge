import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import { apiPost } from '@/services/api';

interface RegisteredCluster {
  id: string;
  name: string;
  register_token: string;
}

export default function ClustersNew() {
  const [form, setForm] = useState({
    name: '',
    description: '',
    kind: 'both' as 'train' | 'eval' | 'both',
    cpu_cores: 8,
    ram_total_mb: 16384,
    disk_total_gb: 200,
    gpu_vendor: 'nvidia' as 'nvidia' | 'rocm' | 'cpu',
    gpu_count: 1,
    gpu_model: '',
    gpu_memory_mb: 24576,
  });
  const [registered, setRegistered] = useState<RegisteredCluster | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError('Cluster name is required');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<RegisteredCluster>('/api/clusters', form);
      setRegistered(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register cluster');
    } finally {
      setLoading(false);
    }
  }

  if (registered) {
    const apiBase = window.location.origin.replace('5173', '8000');
    const installCmd = `docker run -d --name vf-agent \\
  --restart unless-stopped \\
  --gpus all \\
  -e VF_API_URL=${apiBase} \\
  -e VF_CLUSTER_ID=${registered.id} \\
  -e VF_REGISTER_TOKEN=${registered.register_token} \\
  visionforge/agent:latest`;
    return (
      <div className="max-w-2xl space-y-4">
        <h1>Cluster registered</h1>
        <Alert variant="success">
          Run this command on the worker machine to start the agent. The token below appears only once
          — save it now.
        </Alert>
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3">
          <div className="label-overline mb-2">Cluster ID</div>
          <div className="font-mono text-xs text-[var(--hud-text-data)] mb-3">{registered.id}</div>
          <div className="label-overline mb-2">Register token</div>
          <div className="font-mono text-xs text-[var(--hud-text-data)] break-all mb-3">
            {registered.register_token}
          </div>
          <div className="label-overline mb-2">Agent install command</div>
          <pre className="bg-[var(--hud-inset)] border border-[var(--hud-border-subtle)] p-3 text-[0.6875rem] font-mono whitespace-pre-wrap break-all text-[var(--hud-text-data)]">
            {installCmd}
          </pre>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => navigate('/clusters')}>Done</Button>
          <Link to="/clusters">
            <Button variant="outline">Back to clusters</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Clusters / New</div>
          <h1>Register Cluster</h1>
        </div>
        <Link to="/clusters" className="text-xs font-mono text-[var(--hud-accent)] hover:underline">
          ← CLUSTERS
        </Link>
      </div>

      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="label-overline block mb-1">Name</label>
          <Input value={form.name} onChange={(e) => setField('name', e.target.value)} placeholder="gpu-rig-01" />
        </div>
        <div>
          <label className="label-overline block mb-1">Description</label>
          <Input
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            placeholder="On-prem 2× A100 box"
          />
        </div>
        <div>
          <label className="label-overline block mb-1">Workload kind</label>
          <Select value={form.kind} onChange={(e) => setField('kind', e.target.value as typeof form.kind)}>
            <option value="both">Training + Evaluation</option>
            <option value="train">Training only</option>
            <option value="eval">Evaluation only</option>
          </Select>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="label-overline block mb-1">CPU cores</label>
            <Input
              type="number"
              min={1}
              value={form.cpu_cores}
              onChange={(e) => setField('cpu_cores', parseInt(e.target.value) || 0)}
            />
          </div>
          <div>
            <label className="label-overline block mb-1">RAM (MB)</label>
            <Input
              type="number"
              min={0}
              value={form.ram_total_mb}
              onChange={(e) => setField('ram_total_mb', parseInt(e.target.value) || 0)}
            />
          </div>
          <div>
            <label className="label-overline block mb-1">Disk (GB)</label>
            <Input
              type="number"
              min={0}
              value={form.disk_total_gb}
              onChange={(e) => setField('disk_total_gb', parseInt(e.target.value) || 0)}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline block mb-1">GPU vendor</label>
            <Select
              value={form.gpu_vendor}
              onChange={(e) => setField('gpu_vendor', e.target.value as typeof form.gpu_vendor)}
            >
              <option value="nvidia">NVIDIA (CUDA)</option>
              <option value="rocm">AMD (ROCm)</option>
              <option value="cpu">CPU only</option>
            </Select>
          </div>
          <div>
            <label className="label-overline block mb-1">GPU count</label>
            <Input
              type="number"
              min={0}
              value={form.gpu_count}
              onChange={(e) => setField('gpu_count', parseInt(e.target.value) || 0)}
            />
          </div>
          <div>
            <label className="label-overline block mb-1">GPU model</label>
            <Input
              value={form.gpu_model}
              onChange={(e) => setField('gpu_model', e.target.value)}
              placeholder="A100 80GB / RX 7900 XTX"
            />
          </div>
          <div>
            <label className="label-overline block mb-1">GPU memory (MB)</label>
            <Input
              type="number"
              min={0}
              value={form.gpu_memory_mb}
              onChange={(e) => setField('gpu_memory_mb', parseInt(e.target.value) || 0)}
            />
          </div>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <Button type="submit" disabled={loading}>
          {loading ? 'Registering…' : 'Register cluster'}
        </Button>
      </form>
    </div>
  );
}
