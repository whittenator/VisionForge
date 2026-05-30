import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import ClusterSelect from '@/components/common/ClusterSelect';
import SplitPanel, { SplitConfig, DEFAULT_SPLIT } from '@/components/common/SplitPanel';
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

const BASE_MODELS = ['yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt'];

type FieldType = 'number' | 'bool' | 'select';
interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  default: number | boolean | string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  help?: string;
}

// Single source of truth for every tunable hyperparameter / augmentation knob.
// Adding a field here exposes it in the UI and forwards it to the backend.
const GROUPS: { title: string; fields: FieldDef[] }[] = [
  {
    title: 'Core',
    fields: [
      { key: 'epochs', label: 'Epochs', type: 'number', default: 50, min: 1, max: 2000 },
      { key: 'batch', label: 'Batch Size', type: 'number', default: 16, min: 1, max: 512 },
      {
        key: 'imgsz',
        label: 'Image Size',
        type: 'number',
        default: 640,
        min: 32,
        max: 1920,
        step: 32,
      },
      {
        key: 'patience',
        label: 'Patience',
        type: 'number',
        default: 100,
        min: 0,
        max: 1000,
        help: 'Early-stop after N epochs w/o improvement',
      },
      { key: 'seed', label: 'Seed', type: 'number', default: 0, min: 0 },
      {
        key: 'rect',
        label: 'Rectangular',
        type: 'bool',
        default: false,
        help: 'Rectangular batches (min padding)',
      },
      { key: 'single_cls', label: 'Single class', type: 'bool', default: false },
    ],
  },
  {
    title: 'Optimizer & Schedule',
    fields: [
      {
        key: 'optimizer',
        label: 'Optimizer',
        type: 'select',
        default: 'auto',
        options: ['auto', 'SGD', 'Adam', 'AdamW', 'NAdam', 'RAdam', 'RMSProp'],
      },
      {
        key: 'lr0',
        label: 'Initial LR (lr0)',
        type: 'number',
        default: 0.01,
        min: 0.00001,
        max: 1,
        step: 0.0001,
      },
      {
        key: 'lrf',
        label: 'Final LR (lrf)',
        type: 'number',
        default: 0.01,
        min: 0.00001,
        max: 1,
        step: 0.0001,
      },
      {
        key: 'momentum',
        label: 'Momentum',
        type: 'number',
        default: 0.937,
        min: 0,
        max: 1,
        step: 0.001,
      },
      {
        key: 'weight_decay',
        label: 'Weight Decay',
        type: 'number',
        default: 0.0005,
        min: 0,
        max: 0.1,
        step: 0.0001,
      },
      {
        key: 'warmup_epochs',
        label: 'Warmup Epochs',
        type: 'number',
        default: 3.0,
        min: 0,
        max: 20,
        step: 0.5,
      },
      {
        key: 'warmup_momentum',
        label: 'Warmup Momentum',
        type: 'number',
        default: 0.8,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        key: 'warmup_bias_lr',
        label: 'Warmup Bias LR',
        type: 'number',
        default: 0.1,
        min: 0,
        max: 1,
        step: 0.01,
      },
      { key: 'cos_lr', label: 'Cosine LR', type: 'bool', default: false },
      {
        key: 'close_mosaic',
        label: 'Close Mosaic',
        type: 'number',
        default: 10,
        min: 0,
        max: 100,
        help: 'Disable mosaic for last N epochs',
      },
      { key: 'nbs', label: 'Nominal Batch', type: 'number', default: 64, min: 1, max: 256 },
      { key: 'amp', label: 'AMP', type: 'bool', default: true, help: 'Automatic mixed precision' },
    ],
  },
  {
    title: 'Regularization & Loss Gains',
    fields: [
      {
        key: 'dropout',
        label: 'Dropout',
        type: 'number',
        default: 0.0,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        key: 'label_smoothing',
        label: 'Label Smoothing',
        type: 'number',
        default: 0.0,
        min: 0,
        max: 1,
        step: 0.01,
      },
      { key: 'box', label: 'Box Gain', type: 'number', default: 7.5, min: 0, max: 20, step: 0.1 },
      { key: 'cls', label: 'Cls Gain', type: 'number', default: 0.5, min: 0, max: 10, step: 0.1 },
      { key: 'dfl', label: 'DFL Gain', type: 'number', default: 1.5, min: 0, max: 10, step: 0.1 },
      { key: 'overlap_mask', label: 'Overlap Mask', type: 'bool', default: true },
      { key: 'mask_ratio', label: 'Mask Ratio', type: 'number', default: 4, min: 1, max: 16 },
    ],
  },
  {
    title: 'Augmentation',
    fields: [
      {
        key: 'hsv_h',
        label: 'hsv_h',
        type: 'number',
        default: 0.015,
        min: 0,
        max: 1,
        step: 0.001,
        help: 'Hue jitter fraction',
      },
      {
        key: 'hsv_s',
        label: 'hsv_s',
        type: 'number',
        default: 0.7,
        min: 0,
        max: 1,
        step: 0.01,
        help: 'Saturation jitter',
      },
      {
        key: 'hsv_v',
        label: 'hsv_v',
        type: 'number',
        default: 0.4,
        min: 0,
        max: 1,
        step: 0.01,
        help: 'Value jitter',
      },
      {
        key: 'degrees',
        label: 'degrees',
        type: 'number',
        default: 0.0,
        min: 0,
        max: 180,
        step: 1,
        help: 'Rotation range',
      },
      {
        key: 'translate',
        label: 'translate',
        type: 'number',
        default: 0.1,
        min: 0,
        max: 1,
        step: 0.01,
      },
      { key: 'scale', label: 'scale', type: 'number', default: 0.5, min: 0, max: 1, step: 0.01 },
      { key: 'shear', label: 'shear', type: 'number', default: 0.0, min: 0, max: 10, step: 0.1 },
      {
        key: 'perspective',
        label: 'perspective',
        type: 'number',
        default: 0.0,
        min: 0,
        max: 0.001,
        step: 0.0001,
      },
      { key: 'flipud', label: 'flipud', type: 'number', default: 0.0, min: 0, max: 1, step: 0.01 },
      { key: 'fliplr', label: 'fliplr', type: 'number', default: 0.5, min: 0, max: 1, step: 0.01 },
      { key: 'bgr', label: 'bgr', type: 'number', default: 0.0, min: 0, max: 1, step: 0.01 },
      { key: 'mosaic', label: 'mosaic', type: 'number', default: 1.0, min: 0, max: 1, step: 0.01 },
      { key: 'mixup', label: 'mixup', type: 'number', default: 0.0, min: 0, max: 1, step: 0.01 },
      {
        key: 'copy_paste',
        label: 'copy_paste',
        type: 'number',
        default: 0.0,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        key: 'erasing',
        label: 'erasing',
        type: 'number',
        default: 0.4,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        key: 'crop_fraction',
        label: 'crop_fraction',
        type: 'number',
        default: 1.0,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        key: 'auto_augment',
        label: 'auto_augment',
        type: 'select',
        default: 'randaugment',
        options: ['randaugment', 'autoaugment', 'augmix'],
      },
    ],
  },
];

const DEVICES = ['cpu', 'cuda', 'mps', '0', '0,1'];

function buildDefaults(): Record<string, number | boolean | string> {
  const out: Record<string, number | boolean | string> = {};
  for (const g of GROUPS) for (const f of g.fields) out[f.key] = f.default;
  return out;
}

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="label-overline block mb-1">
      {children}
    </label>
  );
}

function HpField({
  field,
  value,
  onChange,
}: {
  field: FieldDef;
  value: number | boolean | string;
  onChange: (v: number | boolean | string) => void;
}) {
  if (field.type === 'bool') {
    return (
      <label className="flex items-center gap-2 pt-5 text-xs font-mono text-[var(--hud-text-muted)]">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        {field.label}
      </label>
    );
  }
  if (field.type === 'select') {
    return (
      <div>
        <FieldLabel htmlFor={`hp-${field.key}`}>{field.label}</FieldLabel>
        <Select
          id={`hp-${field.key}`}
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
        >
          {field.options!.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </Select>
      </div>
    );
  }
  return (
    <div>
      <FieldLabel htmlFor={`hp-${field.key}`}>{field.label}</FieldLabel>
      <Input
        id={`hp-${field.key}`}
        type="number"
        min={field.min}
        max={field.max}
        step={field.step ?? 1}
        value={value as number}
        onChange={(e) => {
          const n = parseFloat(e.target.value);
          onChange(Number.isFinite(n) ? n : (field.default as number));
        }}
        title={field.help}
      />
    </div>
  );
}

export default function ExperimentsNew() {
  const [searchParams] = useSearchParams();
  const preselectedProject = searchParams.get('projectId') || '';

  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [run, setRun] = useState({
    projectId: preselectedProject,
    datasetId: '',
    datasetVersionId: '',
    name: 'Baseline',
    task: 'detect',
    baseModel: 'yolov8n.pt',
    clusterId: '',
    device: 'cpu',
  });
  const [params, setParams] = useState<Record<string, number | boolean | string>>(buildDefaults());
  const [splitCfg, setSplitCfg] = useState<SplitConfig>(DEFAULT_SPLIT);
  const [open, setOpen] = useState<Record<string, boolean>>({ Core: true });
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiGet<{ items: Project[] }>('/api/projects?page=1&page_size=200')
      .then((d) => setProjects(d.items || []))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!run.projectId) {
      setDatasets([]);
      return;
    }
    apiGet<{ items: Dataset[] }>(`/api/datasets?project_id=${run.projectId}&page=1&page_size=200`)
      .then((d) => setDatasets(d.items || []))
      .catch(console.error);
  }, [run.projectId]);

  function setParam(key: string, value: number | boolean | string) {
    setParams((prev) => ({ ...prev, [key]: value }));
  }

  function resetGroup(title: string) {
    const group = GROUPS.find((g) => g.title === title);
    if (!group) return;
    setParams((prev) => {
      const next = { ...prev };
      for (const f of group.fields) next[f.key] = f.default;
      return next;
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!run.projectId) return setError('Select a project');
    if (!run.datasetVersionId) return setError('Select a dataset/version');
    setLoading(true);
    setError(null);
    try {
      // Persist the split first so what we train on matches what we visualize.
      if (run.datasetId && run.datasetVersionId) {
        try {
          await apiPost(
            `/api/datasets/${run.datasetId}/versions/${run.datasetVersionId}/split`,
            splitCfg,
          );
        } catch {
          /* training re-resolves deterministically from the same seed/ratios */
        }
      }
      const job = await apiPost<{ id: string; status: string }>('/api/train', {
        projectId: run.projectId,
        datasetVersionId: run.datasetVersionId,
        task: run.task,
        baseModel: run.baseModel,
        name: run.name,
        clusterId: run.clusterId || null,
        params: {
          ...params,
          device: run.device,
          split_train: splitCfg.train,
          split_val: splitCfg.val,
          split_test: splitCfg.test,
          split_seed: splitCfg.seed,
          split_stratify: splitCfg.stratify,
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
    <div className="max-w-2xl space-y-0">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3 mb-4">
        <div>
          <div className="label-overline mb-0.5">// Experiments / New</div>
          <h1>New Training Run</h1>
        </div>
        <Link
          to="/experiments"
          className="text-xs font-mono text-[var(--hud-accent)] hover:underline"
        >
          ← EXPERIMENTS
        </Link>
      </div>

      <form onSubmit={onSubmit} className="space-y-0">
        {/* Run config */}
        <Section title="Run Configuration" accent>
          <div className="p-4 space-y-3">
            <div>
              <FieldLabel htmlFor="run-name">Run Name</FieldLabel>
              <Input
                id="run-name"
                value={run.name}
                onChange={(e) => setRun((r) => ({ ...r, name: e.target.value }))}
                placeholder="Baseline"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="project-select">Project</FieldLabel>
                <Select
                  id="project-select"
                  value={run.projectId}
                  onChange={(e) =>
                    setRun((r) => ({
                      ...r,
                      projectId: e.target.value,
                      datasetId: '',
                      datasetVersionId: '',
                    }))
                  }
                >
                  <option value="">— select —</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="dataset-select">Dataset Version</FieldLabel>
                <Select
                  id="dataset-select"
                  value={run.datasetVersionId}
                  onChange={(e) => {
                    const ds = datasets.find(
                      (d) => (d.latest_version_id || d.id) === e.target.value,
                    );
                    setRun((r) => ({
                      ...r,
                      datasetVersionId: e.target.value,
                      datasetId: ds?.id || '',
                    }));
                  }}
                  disabled={!run.projectId || datasets.length === 0}
                >
                  <option value="">— select —</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.latest_version_id || d.id}>
                      {d.name}
                      {!d.latest_version_id ? ' (no versions)' : ''}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="task-select">Task</FieldLabel>
                <Select
                  id="task-select"
                  value={run.task}
                  onChange={(e) => setRun((r) => ({ ...r, task: e.target.value }))}
                >
                  <option value="detect">Object Detection</option>
                  <option value="classify">Classification</option>
                  <option value="segment">Segmentation</option>
                  <option value="pose">Pose Estimation</option>
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="base-model">Base Model</FieldLabel>
                <Select
                  id="base-model"
                  value={run.baseModel}
                  onChange={(e) => setRun((r) => ({ ...r, baseModel: e.target.value }))}
                >
                  {BASE_MODELS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div>
              <FieldLabel htmlFor="device">Device</FieldLabel>
              <Select
                id="device"
                value={run.device}
                onChange={(e) => setRun((r) => ({ ...r, device: e.target.value }))}
              >
                {DEVICES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </Section>

        {/* Dataset split */}
        <Section title="Dataset Split" accent>
          <div className="p-4">
            <SplitPanel
              datasetId={run.datasetId}
              versionId={run.datasetVersionId}
              onConfigChange={setSplitCfg}
            />
          </div>
        </Section>

        {/* Cluster */}
        <Section title="Compute Cluster" accent>
          <div className="p-4 space-y-2">
            <FieldLabel htmlFor="cluster-select">Run on cluster</FieldLabel>
            <ClusterSelect
              id="cluster-select"
              kind="train"
              value={run.clusterId}
              onChange={(v) => setRun((r) => ({ ...r, clusterId: v }))}
              allowAuto
            />
            <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
              Pick an idle cluster to dedicate this run, or leave on auto-assign. Busy clusters are
              disabled.
            </p>
          </div>
        </Section>

        {/* Hyperparameter groups */}
        {GROUPS.map((g) => (
          <Section
            key={g.title}
            title={g.title}
            collapsible
            isOpen={!!open[g.title]}
            onToggle={() => setOpen((o) => ({ ...o, [g.title]: !o[g.title] }))}
            onReset={() => resetGroup(g.title)}
          >
            {open[g.title] && (
              <div className="p-4 grid grid-cols-2 gap-3 md:grid-cols-3">
                {g.fields.map((f) => (
                  <HpField
                    key={f.key}
                    field={f}
                    value={params[f.key]}
                    onChange={(v) => setParam(f.key, v)}
                  />
                ))}
              </div>
            )}
          </Section>
        ))}

        {error && (
          <Alert variant="error" className="mt-3">
            {error}
          </Alert>
        )}

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

function Section({
  title,
  children,
  accent,
  collapsible,
  isOpen,
  onToggle,
  onReset,
}: {
  title: string;
  children: React.ReactNode;
  accent?: boolean;
  collapsible?: boolean;
  isOpen?: boolean;
  onToggle?: () => void;
  onReset?: () => void;
}) {
  return (
    <div className="border border-t-0 first:border-t border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
      <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center justify-between">
        <button
          type="button"
          onClick={onToggle}
          disabled={!collapsible}
          className="flex items-center gap-2 disabled:cursor-default"
        >
          <div
            className={`h-1.5 w-1.5 ${accent ? 'bg-[var(--hud-accent)]' : 'bg-[var(--hud-border-strong)]'}`}
          />
          <span className="label-overline">{title}</span>
          {collapsible && (
            <span className="text-xs font-mono text-[var(--hud-text-muted)]">
              {isOpen ? '▲' : '▼'}
            </span>
          )}
        </button>
        {collapsible && onReset && isOpen && (
          <button
            type="button"
            onClick={onReset}
            className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)] hover:text-[var(--hud-accent)]"
          >
            RESET
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
