import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Badge from '@/components/ui/Badge';
import { apiPost } from '@/services/api';

interface DiscoveredCluster {
  id: string;
  name: string;
  cpu_cores: number;
  ram_total_mb: number;
  disk_total_gb: number;
  gpu_vendor: 'nvidia' | 'rocm' | 'cpu';
  gpu_count: number;
  gpu_model?: string | null;
  gpu_memory_mb: number;
  agent_host?: string | null;
  agent_port?: number | null;
  agent_version?: string | null;
  os_name?: string | null;
  os_release?: string | null;
  arch?: string | null;
  register_token: string;
}

function randomToken(): string {
  // 32-byte URL-safe token, generated client-side so the operator never has to
  // think one up. The agent reads this value as VF_AGENT_TOKEN.
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

export default function ClustersNew() {
  const navigate = useNavigate();
  const [agentToken] = useState<string>(() => randomToken());
  const [form, setForm] = useState({
    name: '',
    host: '',
    port: 9443,
    kind: 'both' as 'train' | 'eval' | 'both',
    description: '',
    scheme: 'http' as 'http' | 'https',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registered, setRegistered] = useState<DiscoveredCluster | null>(null);

  const installCmd = useMemo(() => {
    const apiBase = window.location.origin.replace(':5173', ':8000');
    return `docker run -d --name vf-agent \\
  --restart unless-stopped \\
  --gpus all \\
  -p 9443:9443 \\
  -v vf-agent-state:/var/lib/vf-agent \\
  -e VF_AGENT_TOKEN=${agentToken} \\
  -e REDIS_URL=${apiBase.replace(/:\d+$/, ':6379')}/0 \\
  visionforge/agent:latest`;
  }, [agentToken]);

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.name.trim()) return setError('Cluster name is required');
    if (!form.host.trim()) return setError('Host (IP or hostname) is required');
    setLoading(true);
    try {
      const res = await apiPost<DiscoveredCluster>('/api/clusters/discover', {
        name: form.name,
        host: form.host,
        port: form.port,
        agent_token: agentToken,
        kind: form.kind,
        description: form.description || undefined,
        scheme: form.scheme,
      });
      setRegistered(res);
    } catch (err) {
      // The API returns 502 with detail "<message> [reason=<code>]" for
      // agent-unreachable errors; surface a human-readable hint for the code.
      const raw = err instanceof Error ? err.message : 'Failed to register cluster';
      const m = raw.match(/\[reason=([a-z_]+)\]/);
      const hint =
        m?.[1] === 'connect'
          ? ' (host or port unreachable)'
          : m?.[1] === 'timeout'
            ? ' (agent did not respond in time)'
            : m?.[1] === 'auth'
              ? ' (agent rejected the token)'
              : m?.[1] === 'bad_response'
                ? ' (agent returned malformed data)'
                : '';
      setError(`${raw}${hint}`);
    } finally {
      setLoading(false);
    }
  }

  if (registered) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
          <div>
            <div className="label-overline mb-0.5">// Clusters / Registered</div>
            <h1>Cluster registered</h1>
          </div>
        </div>
        <Alert variant="success">
          Specs discovered from the agent at {registered.agent_host}:{registered.agent_port}. The
          agent has been adopted and will start posting heartbeats within {30}s.
        </Alert>
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3 space-y-3">
          <div>
            <div className="label-overline mb-1">Cluster</div>
            <div className="text-sm text-[var(--hud-text-primary)]">{registered.name}</div>
            <div className="font-mono text-[0.6875rem] text-[var(--hud-text-data)]">
              {registered.id}
            </div>
          </div>
          <div>
            <div className="label-overline mb-1">Discovered hardware</div>
            <div className="flex flex-wrap gap-1">
              <Badge variant="info">{registered.cpu_cores} CPU cores</Badge>
              <Badge variant="info">{(registered.ram_total_mb / 1024).toFixed(1)} GB RAM</Badge>
              <Badge variant="info">{registered.disk_total_gb} GB disk</Badge>
              {registered.gpu_count > 0 && (
                <Badge variant="success">
                  {registered.gpu_vendor.toUpperCase()} · {registered.gpu_count}× {registered.gpu_model || 'GPU'}
                </Badge>
              )}
              {registered.os_name && (
                <Badge variant="default">
                  {registered.os_name} {registered.os_release || ''} · {registered.arch || ''}
                </Badge>
              )}
              {registered.agent_version && (
                <Badge variant="default">agent v{registered.agent_version}</Badge>
              )}
            </div>
          </div>
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
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Clusters / New</div>
          <h1>Register Cluster</h1>
          <p className="text-xs text-[var(--hud-text-muted)] mt-1">
            VisionForge auto-discovers hardware from a running agent. Install the agent first,
            then enter the worker's IP below.
          </p>
        </div>
        <Link
          to="/clusters"
          className="text-xs font-mono text-[var(--hud-accent)] hover:underline"
        >
          ← CLUSTERS
        </Link>
      </div>

      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3 space-y-2">
        <div className="label-overline">Step 1 · Install the agent on the worker machine</div>
        <p className="text-[0.75rem] text-[var(--hud-text-muted)]">
          Run this command on the worker. It pulls the agent image, generates a random
          authentication token (already filled below), and exposes the agent's discovery API on
          port <span className="font-mono">9443</span>.
        </p>
        <pre className="bg-[var(--hud-inset)] border border-[var(--hud-border-subtle)] p-3 text-[0.6875rem] font-mono whitespace-pre-wrap break-all text-[var(--hud-text-data)]">
          {installCmd}
        </pre>
        <p className="text-[0.6875rem] text-[var(--hud-text-muted)]">
          The agent stays in <span className="font-mono">unadopted</span> mode until you complete
          Step 2; before then it accepts no jobs.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-3 border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3"
      >
        <div className="label-overline">Step 2 · Register the cluster</div>
        <div>
          <label className="label-overline block mb-1">Name</label>
          <Input
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="gpu-rig-01"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline block mb-1">Host (IP / hostname)</label>
            <Input
              value={form.host}
              onChange={(e) => setField('host', e.target.value)}
              placeholder="10.0.0.10"
            />
          </div>
          <div>
            <label className="label-overline block mb-1">Port</label>
            <Input
              type="number"
              min={1}
              max={65535}
              value={form.port}
              onChange={(e) => setField('port', parseInt(e.target.value) || 9443)}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline block mb-1">Scheme</label>
            <Select
              value={form.scheme}
              onChange={(e) => setField('scheme', e.target.value as typeof form.scheme)}
            >
              <option value="http">http (private network)</option>
              <option value="https">https</option>
            </Select>
          </div>
          <div>
            <label className="label-overline block mb-1">Workload kind</label>
            <Select
              value={form.kind}
              onChange={(e) => setField('kind', e.target.value as typeof form.kind)}
            >
              <option value="both">Training + Evaluation</option>
              <option value="train">Training only</option>
              <option value="eval">Evaluation only</option>
            </Select>
          </div>
        </div>
        <div>
          <label className="label-overline block mb-1">Description (optional)</label>
          <Input
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            placeholder="On-prem 2× A100 box"
          />
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <Button type="submit" disabled={loading}>
          {loading ? 'Probing agent…' : 'Discover & register'}
        </Button>
      </form>
    </div>
  );
}
