import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/common/EmptyState';
import ErrorState from '@/components/common/ErrorState';
import { apiGet } from '@/services/api';

interface Gpu {
  index: number;
  name?: string | null;
  memory_mb: number;
  util_pct: number;
  mem_used_mb: number;
  temperature_c?: number | null;
}

interface Cluster {
  id: string;
  name: string;
  description?: string | null;
  kind: 'train' | 'eval' | 'both';
  status: 'online' | 'offline' | 'busy' | 'error';
  enabled: boolean;
  cpu_cores: number;
  ram_total_mb: number;
  disk_total_gb: number;
  gpu_vendor: 'nvidia' | 'rocm' | 'cpu';
  gpu_count: number;
  gpu_model?: string | null;
  gpu_memory_mb: number;
  cpu_usage_pct: number;
  ram_used_mb: number;
  disk_used_gb: number;
  gpu_usage_pct: number;
  active_job_id?: string | null;
  last_heartbeat_at?: string | null;
  gpus: Gpu[];
}

const REFRESH_MS = 5000;

function statusBadge(status: Cluster['status'], enabled: boolean) {
  if (!enabled) return <Badge variant="default">DISABLED</Badge>;
  if (status === 'online') return <Badge variant="success">● ONLINE · IDLE</Badge>;
  if (status === 'busy') return <Badge variant="info">● BUSY</Badge>;
  if (status === 'error') return <Badge variant="danger">● ERROR</Badge>;
  return <Badge variant="warning">● OFFLINE</Badge>;
}

function vendorBadge(vendor: Cluster['gpu_vendor'], count: number) {
  if (vendor === 'nvidia') return <Badge variant="success">NVIDIA · {count}× GPU</Badge>;
  if (vendor === 'rocm') return <Badge variant="warning">AMD ROCm · {count}× GPU</Badge>;
  return <Badge variant="default">CPU ONLY</Badge>;
}

function kindBadge(kind: Cluster['kind']) {
  const label = kind === 'both' ? 'TRAIN + EVAL' : kind.toUpperCase();
  return <Badge variant="info">{label}</Badge>;
}

function pct(n: number) {
  return `${Math.round(n)}%`;
}
function gb(mb: number) {
  return `${(mb / 1024).toFixed(1)} GB`;
}

function UsageBar({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(100, value));
  const tone =
    v > 90
      ? 'bg-[var(--hud-danger)]'
      : v > 70
        ? 'bg-[var(--hud-warning)]'
        : 'bg-[var(--hud-accent)]';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
        <span>{label}</span>
        <span className="text-[var(--hud-text-data)]">{pct(v)}</span>
      </div>
      <div className="h-1 bg-[var(--hud-inset)] overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}

function ClusterCard({ c }: { c: Cluster }) {
  const ramPct = c.ram_total_mb > 0 ? (c.ram_used_mb / c.ram_total_mb) * 100 : 0;
  const diskPct = c.disk_total_gb > 0 ? (c.disk_used_gb / c.disk_total_gb) * 100 : 0;
  const heartbeatAgo = c.last_heartbeat_at
    ? `${Math.max(0, Math.round((Date.now() - new Date(c.last_heartbeat_at).getTime()) / 1000))}s ago`
    : 'never';

  return (
    <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-[var(--hud-text-primary)] truncate">
            {c.name}
          </div>
          {c.description && (
            <div className="text-[0.6875rem] text-[var(--hud-text-muted)] truncate">
              {c.description}
            </div>
          )}
        </div>
        <div className="flex flex-col gap-1 items-end">
          {statusBadge(c.status, c.enabled)}
          {kindBadge(c.kind)}
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {vendorBadge(c.gpu_vendor, c.gpu_count)}
        {c.gpu_model && (
          <Badge variant="default" className="truncate max-w-[12rem]">
            {c.gpu_model}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <UsageBar value={c.cpu_usage_pct} label={`CPU · ${c.cpu_cores}c`} />
        <UsageBar value={ramPct} label={`RAM · ${gb(c.ram_total_mb)}`} />
        <UsageBar value={diskPct} label={`DISK · ${c.disk_total_gb} GB`} />
        <UsageBar
          value={c.gpu_usage_pct}
          label={`GPU · ${c.gpu_count > 0 ? gb(c.gpu_memory_mb) : 'n/a'}`}
        />
      </div>

      {c.gpus.length > 0 && (
        <div className="border border-[var(--hud-border-subtle)] bg-[var(--hud-inset)] p-2 space-y-1">
          <div className="label-overline">Per-GPU</div>
          {c.gpus.map((g) => (
            <div
              key={g.index}
              className="flex items-center justify-between text-[0.6875rem] font-mono text-[var(--hud-text-muted)]"
            >
              <span className="truncate">
                #{g.index} {g.name || ''}
              </span>
              <span className="text-[var(--hud-text-data)]">
                {pct(g.util_pct)} · {(g.mem_used_mb / 1024).toFixed(1)}/
                {(g.memory_mb / 1024).toFixed(1)}GB
                {g.temperature_c != null ? ` · ${Math.round(g.temperature_c)}°C` : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-[0.6875rem] font-mono text-[var(--hud-text-muted)] pt-1 border-t border-[var(--hud-border-subtle)]">
        <span>HEARTBEAT · {heartbeatAgo}</span>
        {c.active_job_id && (
          <span className="text-[var(--hud-info-text)]">JOB · {c.active_job_id.slice(0, 8)}</span>
        )}
      </div>
    </div>
  );
}

export default function ClustersIndex() {
  const [clusters, setClusters] = useState<Cluster[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiGet<Cluster[]>('/api/clusters');
        if (!cancelled) {
          setClusters(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load clusters');
      }
    }
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Clusters</div>
          <h1>Compute Clusters</h1>
          <p className="text-xs text-[var(--hud-text-muted)] mt-1">
            Live view of training and evaluation workers. Resource telemetry refreshes every {REFRESH_MS / 1000}s.
          </p>
        </div>
        <Link to="/clusters/new">
          <Button>+ REGISTER CLUSTER</Button>
        </Link>
      </div>

      {error && <ErrorState description={error} />}

      {clusters === null && !error && (
        <div className="flex items-center gap-2 text-xs font-mono text-[var(--hud-text-muted)]">
          <Spinner size={14} /> Loading clusters…
        </div>
      )}

      {clusters && clusters.length === 0 && (
        <EmptyState
          title="No clusters registered"
          description="Register a worker by running the agent with the token from + REGISTER CLUSTER."
        />
      )}

      {clusters && clusters.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {clusters.map((c) => (
            <ClusterCard key={c.id} c={c} />
          ))}
        </div>
      )}
    </div>
  );
}
