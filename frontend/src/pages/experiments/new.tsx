import React, { useState, useEffect, useMemo } from 'react';
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
interface PriorRun {
  id: string;
  name?: string;
  status?: string;
}

// Field schema, mirroring the backend FieldDef shape. The training form is
// rendered entirely from the capabilities the backend reports, so no framework
// (Ultralytics, Timm, …) is hard-coded here.
type FieldType = 'number' | 'bool' | 'select' | 'text' | 'model';
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
interface FieldGroup {
  title: string;
  fields: FieldDef[];
}
interface FrameworkCapabilities {
  key: string;
  label: string;
  supported_tasks: string[];
  models_by_task: Record<string, string[]>;
  groups: FieldGroup[];
  device_options: string[];
  supports_resume?: boolean;
}

const TASK_LABELS: Record<string, string> = {
  detect: 'Object Detection',
  classify: 'Classification',
  segment: 'Segmentation',
  pose: 'Pose Estimation',
};

function buildDefaults(groups: FieldGroup[]): Record<string, number | boolean | string> {
  const out: Record<string, number | boolean | string> = {};
  for (const g of groups) for (const f of g.fields) out[f.key] = f.default;
  return out;
}

function hasModelField(groups: FieldGroup[]): boolean {
  return groups.some((g) => g.fields.some((f) => f.type === 'model'));
}

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="label-overline block mb-1">
      {children}
    </label>
  );
}

// Searchable picker for frameworks with large catalogues (e.g. Timm's ~1300
// architectures). Queries the backend model-search endpoint as the user types.
function SearchableModel({
  frameworkKey,
  task,
  value,
  onChange,
  id,
}: {
  frameworkKey: string;
  task: string;
  value: string;
  onChange: (v: string) => void;
  id: string;
}) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<string[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    const handle = setTimeout(() => {
      apiGet<{ items: string[] }>(
        `/api/training/frameworks/${frameworkKey}/models?task=${task}&query=${encodeURIComponent(query)}`,
      )
        .then((d) => active && setResults(d.items || []))
        .catch(() => active && setResults([]));
    }, 250);
    return () => {
      active = false;
      clearTimeout(handle);
    };
  }, [query, frameworkKey, task]);

  return (
    <div className="relative">
      <Input
        id={id}
        value={query}
        placeholder="Search architectures…"
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto border border-[var(--hud-border-default)] bg-[var(--hud-surface)] text-xs font-mono">
          {results.map((m) => (
            <li key={m}>
              <button
                type="button"
                className={`block w-full px-2 py-1 text-left hover:bg-[var(--hud-bg-hover)] ${m === value ? 'text-[var(--hud-accent)]' : 'text-[var(--hud-text-data)]'}`}
                onMouseDown={() => {
                  onChange(m);
                  setQuery(m);
                  setOpen(false);
                }}
              >
                {m}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function HpField({
  field,
  value,
  onChange,
  frameworkKey,
  task,
}: {
  field: FieldDef;
  value: number | boolean | string;
  onChange: (v: number | boolean | string) => void;
  frameworkKey: string;
  task: string;
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
              {o || '(none)'}
            </option>
          ))}
        </Select>
      </div>
    );
  }
  if (field.type === 'model') {
    return (
      <div className="col-span-2 md:col-span-3">
        <FieldLabel htmlFor={`hp-${field.key}`}>{field.label}</FieldLabel>
        <SearchableModel
          id={`hp-${field.key}`}
          frameworkKey={frameworkKey}
          task={task}
          value={String(value)}
          onChange={onChange}
        />
        {field.help && (
          <p className="mt-1 text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
            {field.help}
          </p>
        )}
      </div>
    );
  }
  if (field.type === 'text') {
    return (
      <div>
        <FieldLabel htmlFor={`hp-${field.key}`}>{field.label}</FieldLabel>
        <Input
          id={`hp-${field.key}`}
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          title={field.help}
        />
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
  const [priorRuns, setPriorRuns] = useState<PriorRun[]>([]);
  const [resumeFrom, setResumeFrom] = useState('');
  const [frameworks, setFrameworks] = useState<FrameworkCapabilities[]>([]);
  const [run, setRun] = useState({
    projectId: preselectedProject,
    datasetId: '',
    datasetVersionId: '',
    name: 'Baseline',
    framework: '',
    task: '',
    baseModel: '',
    clusterId: '',
    device: 'cpu',
  });
  const [params, setParams] = useState<Record<string, number | boolean | string>>({});
  const [splitCfg, setSplitCfg] = useState<SplitConfig>(DEFAULT_SPLIT);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const caps = useMemo(
    () => frameworks.find((f) => f.key === run.framework),
    [frameworks, run.framework],
  );

  useEffect(() => {
    apiGet<{ items: Project[] }>('/api/projects?page=1&page_size=200')
      .then((d) => setProjects(d.items || []))
      .catch(console.error);
  }, []);

  // Load the available training frameworks and initialise the form from the
  // first one (default Ultralytics, so the page looks unchanged for YOLO users).
  useEffect(() => {
    apiGet<{ items: FrameworkCapabilities[] }>('/api/training/frameworks')
      .then((d) => {
        const items = d.items || [];
        setFrameworks(items);
        const def = items.find((f) => f.key === 'ultralytics') || items[0];
        if (def) selectFramework(def, items);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load frameworks'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectFramework(fw: FrameworkCapabilities, all?: FrameworkCapabilities[]) {
    const task = fw.supported_tasks[0] || 'classify';
    const models = fw.models_by_task[task] || [];
    setRun((r) => ({
      ...r,
      framework: fw.key,
      task,
      baseModel: hasModelField(fw.groups) ? '' : models[0] || '',
      device: fw.device_options[0] || 'cpu',
    }));
    setParams(buildDefaults(fw.groups));
    setOpen({ [fw.groups[0]?.title || '']: true });
    void all;
  }

  useEffect(() => {
    if (!run.projectId) {
      setDatasets([]);
      setPriorRuns([]);
      setResumeFrom('');
      return;
    }
    apiGet<{ items: Dataset[] }>(`/api/datasets?project_id=${run.projectId}&page=1&page_size=200`)
      .then((d) => setDatasets(d.items || []))
      .catch(console.error);
    // Prior runs in this project are candidates to resume training from.
    apiGet<{ items: PriorRun[] }>(
      `/api/experiments/runs?project_id=${run.projectId}&page=1&page_size=100`,
    )
      .then((d) => setPriorRuns(d.items || []))
      .catch(() => setPriorRuns([]));
    setResumeFrom('');
  }, [run.projectId]);

  function setParam(key: string, value: number | boolean | string) {
    setParams((prev) => ({ ...prev, [key]: value }));
  }

  function resetGroup(title: string) {
    const group = caps?.groups.find((g) => g.title === title);
    if (!group) return;
    setParams((prev) => {
      const next = { ...prev };
      for (const f of group.fields) next[f.key] = f.default;
      return next;
    });
  }

  function onTaskChange(task: string) {
    const models = caps?.models_by_task[task] || [];
    setRun((r) => ({
      ...r,
      task,
      baseModel: caps && hasModelField(caps.groups) ? r.baseModel : models[0] || '',
    }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!run.projectId) return setError('Select a project');
    if (!run.datasetVersionId) return setError('Select a dataset/version');
    const usesModelField = caps ? hasModelField(caps.groups) : false;
    const baseModel = usesModelField ? String(params.model ?? '') : run.baseModel;
    setLoading(true);
    setError(null);
    try {
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
        framework: run.framework,
        baseModel,
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
          ...(resumeFrom ? { resume_from: resumeFrom } : {}),
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

  const usesModelField = caps ? hasModelField(caps.groups) : false;
  const baseModelOptions = caps?.models_by_task[run.task] || [];

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
                <FieldLabel htmlFor="framework-select">Training Framework</FieldLabel>
                <Select
                  id="framework-select"
                  value={run.framework}
                  onChange={(e) => {
                    const fw = frameworks.find((f) => f.key === e.target.value);
                    if (fw) selectFramework(fw);
                  }}
                >
                  {frameworks.map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="task-select">Task</FieldLabel>
                <Select
                  id="task-select"
                  value={run.task}
                  onChange={(e) => onTaskChange(e.target.value)}
                >
                  {(caps?.supported_tasks || []).map((t) => (
                    <option key={t} value={t}>
                      {TASK_LABELS[t] || t}
                    </option>
                  ))}
                </Select>
              </div>
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
              {!usesModelField && (
                <div>
                  <FieldLabel htmlFor="base-model">Base Model</FieldLabel>
                  <Select
                    id="base-model"
                    value={run.baseModel}
                    onChange={(e) => setRun((r) => ({ ...r, baseModel: e.target.value }))}
                  >
                    {baseModelOptions.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              <div>
                <FieldLabel htmlFor="device">Device</FieldLabel>
                <Select
                  id="device"
                  value={run.device}
                  onChange={(e) => setRun((r) => ({ ...r, device: e.target.value }))}
                >
                  {(caps?.device_options || ['cpu']).map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            {caps?.supports_resume && (
              <div>
                <FieldLabel htmlFor="resume-from">Resume From (optional)</FieldLabel>
                <Select
                  id="resume-from"
                  value={resumeFrom}
                  onChange={(e) => setResumeFrom(e.target.value)}
                  disabled={!run.projectId || priorRuns.length === 0}
                >
                  <option value="">— start fresh —</option>
                  {priorRuns.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name || r.id}
                      {r.status ? ` (${r.status})` : ''}
                    </option>
                  ))}
                </Select>
                <p className="mt-1 text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
                  Continue training from a prior run&apos;s latest checkpoint.
                </p>
              </div>
            )}
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

        {/* Hyperparameter groups (rendered from the framework's capabilities) */}
        {(caps?.groups || []).map((g) => (
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
                    frameworkKey={run.framework}
                    task={run.task}
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
