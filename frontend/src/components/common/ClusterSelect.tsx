import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Select from '@/components/ui/Select';
import { apiGet } from '@/services/api';

export interface ClusterOption {
  id: string;
  name: string;
  kind: 'train' | 'eval' | 'both';
  status: 'online' | 'offline' | 'busy' | 'error';
  enabled: boolean;
  gpu_vendor: 'nvidia' | 'rocm' | 'cpu';
  gpu_count: number;
  gpu_model?: string | null;
  cpu_cores: number;
  ram_total_mb: number;
  available: boolean;
}

interface Props {
  /** Workload kind filter sent to the backend (`/api/clusters/available?kind=...`). */
  kind: 'train' | 'eval';
  value: string;
  onChange: (clusterId: string) => void;
  /** When true, allow selecting an empty value (auto-pick / shared queue). */
  allowAuto?: boolean;
  id?: string;
}

function describe(c: ClusterOption): string {
  const gpu =
    c.gpu_vendor === 'cpu'
      ? 'CPU'
      : `${c.gpu_count}× ${c.gpu_vendor.toUpperCase()}${c.gpu_model ? ` (${c.gpu_model})` : ''}`;
  const ramGb = (c.ram_total_mb / 1024).toFixed(0);
  const status = c.available
    ? 'IDLE'
    : c.status === 'busy'
      ? 'BUSY'
      : c.status === 'offline'
        ? 'OFFLINE'
        : c.status.toUpperCase();
  return `${c.name} · ${gpu} · ${c.cpu_cores}c / ${ramGb}GB · ${status}`;
}

export default function ClusterSelect({ kind, value, onChange, allowAuto = true, id }: Props) {
  const [clusters, setClusters] = useState<ClusterOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<ClusterOption[]>(`/api/clusters/available?kind=${kind}`)
      .then((data) => {
        if (!cancelled) setClusters(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load clusters');
      });
    return () => {
      cancelled = true;
    };
  }, [kind]);

  const available = clusters?.filter((c) => c.available) ?? [];
  const unavailable = clusters?.filter((c) => !c.available) ?? [];

  return (
    <div className="space-y-1">
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {allowAuto && <option value="">— auto-assign (shared queue) —</option>}
        {!allowAuto && available.length === 0 && <option value="">— no clusters available —</option>}
        {available.length > 0 && (
          <optgroup label="Available">
            {available.map((c) => (
              <option key={c.id} value={c.id}>
                {describe(c)}
              </option>
            ))}
          </optgroup>
        )}
        {unavailable.length > 0 && (
          <optgroup label="Unavailable">
            {unavailable.map((c) => (
              <option key={c.id} value={c.id} disabled>
                {describe(c)}
              </option>
            ))}
          </optgroup>
        )}
      </Select>
      {error && (
        <p className="text-[0.6875rem] font-mono text-[var(--hud-danger-text)]">{error}</p>
      )}
      {clusters && clusters.length === 0 && (
        <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
          No clusters registered.{' '}
          <Link to="/clusters/new" className="text-[var(--hud-accent)] hover:underline">
            Register one →
          </Link>
        </p>
      )}
    </div>
  );
}
