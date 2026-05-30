import React, { useEffect, useState, useCallback } from 'react';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { apiGet, apiPost } from '@/services/api';

export interface SplitConfig {
  train: number;
  val: number;
  test: number;
  seed: number;
  stratify: boolean;
}

interface SplitSummary {
  total: number;
  counts: { train: number; val: number; test: number; unassigned: number };
  per_class: Record<string, { train: number; val: number; test: number }>;
  ratios?: { train: number; val: number; test: number };
  seed?: number;
  stratify?: boolean;
}

export const DEFAULT_SPLIT: SplitConfig = {
  train: 0.8,
  val: 0.2,
  test: 0.0,
  seed: 42,
  stratify: true,
};

const SPLIT_COLORS: Record<string, string> = {
  train: 'oklch(0.60 0.10 155)', // green
  val: 'oklch(0.72 0.10 82)', // amber
  test: 'oklch(0.72 0.08 230)', // blue
  unassigned: 'oklch(0.45 0.02 250)', // muted
};

function StackedBar({ counts }: { counts: SplitSummary['counts'] }) {
  const total = counts.train + counts.val + counts.test + counts.unassigned || 1;
  const segs = (['train', 'val', 'test', 'unassigned'] as const)
    .map((k) => ({ k, v: counts[k] }))
    .filter((s) => s.v > 0);
  return (
    <div>
      <div className="flex h-5 w-full overflow-hidden border border-[var(--hud-border-subtle)]">
        {segs.map((s) => (
          <div
            key={s.k}
            style={{ width: `${(s.v / total) * 100}%`, backgroundColor: SPLIT_COLORS[s.k] }}
            title={`${s.k}: ${s.v}`}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs font-mono">
        {(['train', 'val', 'test', 'unassigned'] as const).map((k) => (
          <div key={k} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5"
              style={{ backgroundColor: SPLIT_COLORS[k] }}
            />
            <span className="text-[var(--hud-text-muted)]">{k}</span>
            <span className="text-[var(--hud-text-data)]">{counts[k]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface Props {
  datasetId?: string;
  versionId?: string;
  /** Notifies parent of the current ratio/seed config (for training params). */
  onConfigChange?: (cfg: SplitConfig) => void;
  /** When false, hides the apply/persist controls (read-only display). */
  editable?: boolean;
}

export default function SplitPanel({
  datasetId,
  versionId,
  onConfigChange,
  editable = true,
}: Props) {
  const [cfg, setCfg] = useState<SplitConfig>(DEFAULT_SPLIT);
  const [summary, setSummary] = useState<SplitSummary | null>(null);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sum = cfg.train + cfg.val + cfg.test;
  const ratiosValid = Math.abs(sum - 1) < 0.001 && cfg.train >= 0 && cfg.val >= 0 && cfg.test >= 0;

  useEffect(() => {
    onConfigChange?.(cfg);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.train, cfg.val, cfg.test, cfg.seed, cfg.stratify]);

  const loadSummary = useCallback(() => {
    if (!datasetId || !versionId) return;
    apiGet<SplitSummary>(`/api/datasets/${datasetId}/versions/${versionId}/split`)
      .then((s) => {
        setSummary(s);
        if (s.ratios) {
          setCfg((prev) => ({
            ...prev,
            train: s.ratios!.train,
            val: s.ratios!.val,
            test: s.ratios!.test,
            seed: s.seed ?? prev.seed,
            stratify: s.stratify ?? prev.stratify,
          }));
        }
      })
      .catch(() => setSummary(null));
  }, [datasetId, versionId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  async function applySplit() {
    if (!datasetId || !versionId || !ratiosValid) return;
    setApplying(true);
    setError(null);
    try {
      const s = await apiPost<SplitSummary>(
        `/api/datasets/${datasetId}/versions/${versionId}/split`,
        cfg,
      );
      setSummary(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to assign split');
    } finally {
      setApplying(false);
    }
  }

  function setRatio(key: 'train' | 'val' | 'test', value: number) {
    setCfg((prev) => ({ ...prev, [key]: Number.isFinite(value) ? value : 0 }));
  }

  const topClasses = summary
    ? Object.entries(summary.per_class)
        .filter(([name]) => name !== '__all__' && name !== '__none__')
        .slice(0, 12)
    : [];

  return (
    <div className="space-y-3">
      {editable && (
        <>
          <div className="grid grid-cols-3 gap-3">
            {(['train', 'val', 'test'] as const).map((k) => (
              <div key={k}>
                <label className="label-overline mb-1 block" htmlFor={`split-${k}`}>
                  {k} ratio
                </label>
                <Input
                  id={`split-${k}`}
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={cfg[k]}
                  onChange={(e) => setRatio(k, parseFloat(e.target.value))}
                />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-overline mb-1 block" htmlFor="split-seed">
                seed
              </label>
              <Input
                id="split-seed"
                type="number"
                value={cfg.seed}
                onChange={(e) => setCfg((p) => ({ ...p, seed: parseInt(e.target.value, 10) || 0 }))}
              />
            </div>
            <label className="flex items-end gap-2 pb-2 text-xs font-mono text-[var(--hud-text-muted)]">
              <input
                type="checkbox"
                checked={cfg.stratify}
                onChange={(e) => setCfg((p) => ({ ...p, stratify: e.target.checked }))}
              />
              stratify by class
            </label>
          </div>
          {!ratiosValid && (
            <p className="text-[0.6875rem] font-mono text-[var(--hud-danger-text)]">
              Ratios must be ≥ 0 and sum to 1.0 (current: {sum.toFixed(2)}).
            </p>
          )}
          {error && (
            <p className="text-[0.6875rem] font-mono text-[var(--hud-danger-text)]">{error}</p>
          )}
          {datasetId && versionId && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!ratiosValid || applying}
              onClick={applySplit}
            >
              {applying ? 'Assigning…' : 'Apply & persist split'}
            </Button>
          )}
        </>
      )}

      {summary ? (
        <div className="space-y-3 pt-1">
          <StackedBar counts={summary.counts} />
          {topClasses.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-[var(--hud-text-muted)]">
                    <th className="py-1 pr-4 text-left label-overline">class</th>
                    <th className="py-1 pr-4 text-right label-overline">train</th>
                    <th className="py-1 pr-4 text-right label-overline">val</th>
                    <th className="py-1 text-right label-overline">test</th>
                  </tr>
                </thead>
                <tbody>
                  {topClasses.map(([name, c]) => (
                    <tr key={name} className="border-t border-[var(--hud-border-subtle)]">
                      <td className="py-1 pr-4 text-[var(--hud-text-secondary)]">{name}</td>
                      <td className="py-1 pr-4 text-right text-[var(--hud-text-data)]">
                        {c.train}
                      </td>
                      <td className="py-1 pr-4 text-right text-[var(--hud-text-data)]">{c.val}</td>
                      <td className="py-1 text-right text-[var(--hud-text-data)]">{c.test}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs font-mono text-[var(--hud-text-muted)]">
          {versionId
            ? 'No split assigned yet.'
            : 'Select a dataset version to configure its split.'}
        </p>
      )}
    </div>
  );
}
