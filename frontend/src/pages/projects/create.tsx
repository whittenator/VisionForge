import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import ErrorState from '@/components/common/ErrorState';
import { apiPost } from '@/services/api';

type TaskType = 'detect' | 'classify';

interface ClassRow {
  name: string;
  color?: string;
  description?: string;
}

interface WizardResponse {
  project: { id: string; name: string; task_type: TaskType };
  dataset: { id: string; name: string; task_type: TaskType };
  version: { id: string; version: number };
  classes: string[];
}

const STEPS = [
  { key: 'task',     label: 'Task Type'  },
  { key: 'project',  label: 'Project'    },
  { key: 'classes',  label: 'Classes'    },
  { key: 'dataset',  label: 'Dataset'    },
  { key: 'review',   label: 'Review'     },
] as const;

export default function ProjectsCreate() {
  const navigate = useNavigate();
  const [stepIdx, setStepIdx] = useState(0);
  const [task, setTask] = useState<TaskType | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [classDraft, setClassDraft] = useState('');
  const [datasetName, setDatasetName] = useState('default');
  const [datasetDescription, setDatasetDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const step = STEPS[stepIdx].key;

  const canAdvance = useMemo(() => {
    if (step === 'task') return task !== null;
    if (step === 'project') return name.trim().length > 0;
    if (step === 'classes') return classes.length > 0;
    if (step === 'dataset') return datasetName.trim().length > 0;
    return true;
  }, [step, task, name, classes, datasetName]);

  function next() {
    setError(null);
    if (stepIdx < STEPS.length - 1) setStepIdx(stepIdx + 1);
  }

  function back() {
    setError(null);
    if (stepIdx > 0) setStepIdx(stepIdx - 1);
  }

  function addClass() {
    const trimmed = classDraft.trim();
    if (!trimmed) return;
    if (classes.some((c) => c.name === trimmed)) {
      setError(`class "${trimmed}" already added`);
      return;
    }
    setClasses([...classes, { name: trimmed }]);
    setClassDraft('');
  }

  function removeClass(idx: number) {
    setClasses(classes.filter((_, i) => i !== idx));
  }

  async function submit() {
    if (!task) {
      setError('Pick a task type');
      setStepIdx(0);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiPost<WizardResponse>('/api/projects/wizard', {
        name: name.trim(),
        description: description.trim() || undefined,
        task_type: task,
        dataset_name: datasetName.trim() || 'default',
        dataset_description: datasetDescription.trim() || undefined,
        classes: classes.map((c) => ({
          name: c.name,
          color: c.color,
          description: c.description,
        })),
      });
      navigate(`/projects/${res.project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <div className="label-overline mb-0.5">// Projects / New</div>
        <h1>New Project</h1>
      </div>

      <ol className="flex items-center gap-1 text-xs font-mono">
        {STEPS.map((s, i) => {
          const done = i < stepIdx;
          const active = i === stepIdx;
          return (
            <li key={s.key} className="flex items-center gap-1">
              <span
                className={[
                  'inline-flex h-6 min-w-6 items-center justify-center px-2 border tracking-widest uppercase',
                  active
                    ? 'bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border-[var(--hud-accent)]'
                    : done
                    ? 'bg-[var(--hud-success-dim)] text-[var(--hud-success-text)] border-[var(--hud-success)]'
                    : 'bg-[var(--hud-surface)] text-[var(--hud-text-muted)] border-[var(--hud-border-default)]',
                ].join(' ')}
              >
                {i + 1}. {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <span className="text-[var(--hud-text-muted)]">›</span>
              )}
            </li>
          );
        })}
      </ol>

      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
        <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
          <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
          <span className="label-overline">{STEPS[stepIdx].label}</span>
        </div>
        <div className="p-4 space-y-4 min-h-[280px]">
          {step === 'task' && (
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  value: 'detect' as const,
                  label: 'Object Detection',
                  desc: 'Localise objects with bounding boxes (YOLO detect).',
                },
                {
                  value: 'classify' as const,
                  label: 'Image Classification',
                  desc: 'Assign one label per image (YOLO classify).',
                },
              ].map((o) => {
                const selected = task === o.value;
                return (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => setTask(o.value)}
                    className={[
                      'text-left border p-4 transition-colors',
                      selected
                        ? 'border-[var(--hud-accent)] bg-[var(--hud-elevated)]'
                        : 'border-[var(--hud-border-default)] hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)]',
                    ].join(' ')}
                  >
                    <div className="font-mono text-[0.6875rem] tracking-widest uppercase text-[var(--hud-accent)] mb-1">
                      {o.value}
                    </div>
                    <div className="font-medium text-sm text-[var(--hud-text-primary)]">
                      {o.label}
                    </div>
                    <div className="text-xs text-[var(--hud-text-muted)] mt-1">
                      {o.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {step === 'project' && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label htmlFor="proj-name" className="label-overline block">
                  Project Name <span className="text-[var(--hud-danger-text)]">*</span>
                </label>
                <Input
                  id="proj-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-project"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="proj-desc" className="label-overline block">
                  Description{' '}
                  <span className="text-[var(--hud-text-muted)]">(optional)</span>
                </label>
                <Input
                  id="proj-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description"
                />
              </div>
            </div>
          )}

          {step === 'classes' && (
            <div className="space-y-3">
              <div className="text-xs text-[var(--hud-text-muted)]">
                Define the labels annotators will apply.{' '}
                {task === 'classify'
                  ? 'For classification, each image gets exactly one of these labels.'
                  : 'For detection, every box gets one of these labels.'}
              </div>
              <div className="flex gap-2">
                <Input
                  value={classDraft}
                  onChange={(e) => setClassDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addClass();
                    }
                  }}
                  placeholder="e.g. person"
                />
                <Button onClick={addClass} disabled={!classDraft.trim()}>
                  Add
                </Button>
              </div>
              {classes.length === 0 ? (
                <div className="text-xs font-mono text-[var(--hud-text-muted)] py-3">
                  No classes added yet.
                </div>
              ) : (
                <ul className="border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)]">
                  {classes.map((c, i) => (
                    <li
                      key={c.name}
                      className="flex items-center justify-between px-3 py-2 text-xs font-mono"
                    >
                      <span>
                        <span className="text-[var(--hud-text-muted)] mr-2">
                          {String(i).padStart(2, '0')}
                        </span>
                        <span className="text-[var(--hud-text-primary)]">{c.name}</span>
                      </span>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => removeClass(i)}
                      >
                        Remove
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {step === 'dataset' && (
            <div className="space-y-3">
              <div className="text-xs text-[var(--hud-text-muted)]">
                A first dataset and version will be created so you can start
                uploading images right after the wizard.
              </div>
              <div className="space-y-1.5">
                <label htmlFor="ds-name" className="label-overline block">
                  Dataset Name <span className="text-[var(--hud-danger-text)]">*</span>
                </label>
                <Input
                  id="ds-name"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="default"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="ds-desc" className="label-overline block">
                  Dataset Description{' '}
                  <span className="text-[var(--hud-text-muted)]">(optional)</span>
                </label>
                <Input
                  id="ds-desc"
                  value={datasetDescription}
                  onChange={(e) => setDatasetDescription(e.target.value)}
                  placeholder="What's in this dataset?"
                />
              </div>
            </div>
          )}

          {step === 'review' && (
            <div className="space-y-3 text-xs font-mono">
              <Row label="Task Type" value={(task || '—').toUpperCase()} />
              <Row label="Project Name" value={name} />
              {description && <Row label="Description" value={description} />}
              <Row
                label="Classes"
                value={classes.map((c) => c.name).join(', ') || '—'}
              />
              <Row label="Dataset Name" value={datasetName} />
              {datasetDescription && (
                <Row label="Dataset Desc" value={datasetDescription} />
              )}
            </div>
          )}

          {error && <ErrorState title="Error" description={error} />}
        </div>
        <div className="border-t border-[var(--hud-border-subtle)] px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => navigate('/projects')}>
              Cancel
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={back} disabled={stepIdx === 0}>
              ← Back
            </Button>
            {stepIdx < STEPS.length - 1 ? (
              <Button onClick={next} disabled={!canAdvance}>
                Next →
              </Button>
            ) : (
              <Button onClick={submit} disabled={submitting}>
                {submitting ? 'Creating…' : 'Create Project'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="text-[var(--hud-text-muted)] tracking-widest uppercase min-w-[120px]">
        {label}
      </span>
      <span className="text-[var(--hud-text-primary)]">{value}</span>
    </div>
  );
}
