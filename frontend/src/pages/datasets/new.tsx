import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Select from '@/components/ui/Select';
import Spinner from '@/components/ui/Spinner';
import DataSourcePanel from '@/components/datasets/DataSourcePanel';
import type { ImportResult } from '@/components/datasets/ArchiveImporter';
import { apiGet, apiPost } from '@/services/api';

interface Project {
  id: string;
  name: string;
}

const STEPS = ['Define', 'Add data', 'Review'] as const;

export default function DatasetNew() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(0);

  // Step 1 — define
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(searchParams.get('projectId') || '');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [taskType, setTaskType] = useState('detect');
  const [classesText, setClassesText] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Created dataset
  const [datasetId, setDatasetId] = useState('');
  const [versionId, setVersionId] = useState('');

  // Step 2/3 — running tallies
  const [uploaded, setUploaded] = useState(0);
  const [imports, setImports] = useState<ImportResult[]>([]);

  useEffect(() => {
    apiGet<{ items: Project[] }>('/api/projects?page=1&page_size=200')
      .then((d) => setProjects(d.items || []))
      .catch(() => {});
  }, []);

  async function createDataset() {
    if (!projectId) {
      setError('Select a project');
      return;
    }
    if (!name.trim()) {
      setError('Enter a dataset name');
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const classes = classesText
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean);
      const ds = await apiPost<{ id: string; activeVersionId: string }>(
        `/api/datasets/${projectId}`,
        {
          name: name.trim(),
          description: description.trim() || undefined,
          task_type: taskType,
          classes: classes.length ? classes : undefined,
        }
      );
      setDatasetId(ds.id);
      setVersionId(ds.activeVersionId);
      setStep(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create dataset');
    } finally {
      setCreating(false);
    }
  }

  const importedAssets = imports.reduce((sum, r) => sum + r.asset_count, 0);
  const importedAnnotations = imports.reduce((sum, r) => sum + r.annotation_count, 0);

  return (
    <div className="max-w-2xl space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Datasets / New</div>
          <h1>Create Dataset</h1>
        </div>
        <Link to="/datasets" className="text-xs font-mono text-[var(--hud-accent)] hover:underline">
          ← DATASETS
        </Link>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => {
          const active = i === step;
          const done = i < step;
          return (
            <React.Fragment key={label}>
              <div className="flex items-center gap-2">
                <span
                  className={[
                    'inline-flex h-5 w-5 items-center justify-center border font-mono text-[0.6875rem]',
                    active
                      ? 'border-[var(--hud-accent)] bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)]'
                      : done
                        ? 'border-[var(--hud-success)] text-[var(--hud-success-text)]'
                        : 'border-[var(--hud-border-default)] text-[var(--hud-text-muted)]',
                  ].join(' ')}
                >
                  {done ? '✓' : i + 1}
                </span>
                <span
                  className={[
                    'font-mono text-[0.6875rem] tracking-wide',
                    active ? 'text-[var(--hud-text-primary)]' : 'text-[var(--hud-text-muted)]',
                  ].join(' ')}
                >
                  {label.toUpperCase()}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <span className="h-px w-6 bg-[var(--hud-border-default)]" />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Step 1 — Define */}
      {step === 0 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-overline block mb-1" htmlFor="proj">
                Project
              </label>
              <Select id="proj" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">— select —</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="label-overline block mb-1" htmlFor="task">
                Task type
              </label>
              <Select id="task" value={taskType} onChange={(e) => setTaskType(e.target.value)}>
                <option value="detect">Detection</option>
                <option value="classify">Classification</option>
              </Select>
            </div>
          </div>
          <div>
            <label className="label-overline block mb-1" htmlFor="name">
              Dataset name
            </label>
            <Input
              id="name"
              placeholder="e.g. Traffic signs v1"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && createDataset()}
            />
          </div>
          <div>
            <label className="label-overline block mb-1" htmlFor="desc">
              Description (optional)
            </label>
            <Input
              id="desc"
              placeholder="What this dataset is for"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <label className="label-overline block mb-1" htmlFor="classes">
              Classes (optional, comma-separated)
            </label>
            <Input
              id="classes"
              placeholder="person, car, bicycle"
              value={classesText}
              onChange={(e) => setClassesText(e.target.value)}
            />
          </div>
          {error && <Alert variant="error">{error}</Alert>}
          <Button onClick={createDataset} disabled={creating || !name.trim() || !projectId}>
            {creating ? (
              <span className="flex items-center gap-2">
                <Spinner size={12} />
                Creating…
              </span>
            ) : (
              'Create & continue'
            )}
          </Button>
        </div>
      )}

      {/* Step 2 — Add data */}
      {step === 1 && datasetId && versionId && (
        <div className="space-y-3">
          <DataSourcePanel
            datasetId={datasetId}
            versionId={versionId}
            onUploaded={(c) => setUploaded((n) => n + c)}
            onImported={(r) => setImports((prev) => [...prev, r])}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--hud-text-muted)]">
              {uploaded + importedAssets} asset(s) added so far
            </span>
            <Button onClick={() => setStep(2)}>Continue →</Button>
          </div>
        </div>
      )}

      {/* Step 3 — Review */}
      {step === 2 && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-4 space-y-4">
          <div>
            <span className="label-overline">Summary</span>
            <dl className="mt-2 border border-[var(--hud-border-default)] divide-y divide-[var(--hud-border-subtle)] text-xs font-mono">
              <SummaryRow label="Uploaded images" value={String(uploaded)} />
              <SummaryRow label="Imported assets" value={String(importedAssets)} />
              <SummaryRow label="Imported annotations" value={String(importedAnnotations)} />
            </dl>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => navigate(`/datasets/${datasetId}`)}>Open dataset</Button>
            <Button variant="outline" onClick={() => navigate(`/datasets/${datasetId}/annotate`)}>
              Annotate now →
            </Button>
            <Button variant="ghost" onClick={() => setStep(1)}>
              ← Add more data
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-3 py-2">
      <span className="text-[var(--hud-text-muted)]">{label}</span>
      <span className="text-[var(--hud-text-data)]">{value}</span>
    </div>
  );
}
