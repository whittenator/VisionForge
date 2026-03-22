import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiPost } from '@/services/api';

interface Project { id: string; name: string; }
interface Dataset { id: string; name: string; latest_version_id?: string; }

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="label-overline block mb-1">
      {children}
    </label>
  );
}

export default function ActiveLearningNew() {
  const [searchParams] = useSearchParams();
  const preselectedProject = searchParams.get('projectId') || '';

  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [form, setForm] = useState({
    projectId: preselectedProject,
    datasetVersionId: '',
    strategy: 'uncertainty',
    k: 20,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiGet<Project[]>('/api/projects').then(setProjects).catch(console.error);
  }, []);

  useEffect(() => {
    if (!form.projectId) { setDatasets([]); return; }
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
      const result = await apiPost<{ al_run_id: string; count: number; strategy: string }>(
        '/api/al/select',
        {
          project_id: form.projectId,
          dataset_version_id: form.datasetVersionId,
          strategy: form.strategy,
          k: form.k,
        }
      );
      navigate(`/active-learning/${result.al_run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start AL run');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Active Learning / New</div>
          <h1>New Active Learning Run</h1>
        </div>
        <Link to="/active-learning" className="text-xs font-mono text-[var(--hud-accent)] hover:underline">
          ← AL RUNS
        </Link>
      </div>

      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-3 text-xs text-[var(--hud-text-muted)]">
        Active learning selects the most informative unlabeled samples from your dataset so annotators
        focus effort where it matters most. The selected items are added to an AL run for annotation.
      </div>

      <form onSubmit={onSubmit} className="space-y-0">
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="label-overline">Configuration</span>
          </div>
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="project-select">Project</FieldLabel>
                <Select
                  id="project-select"
                  value={form.projectId}
                  onChange={(e) => { setField('projectId', e.target.value); setField('datasetVersionId', ''); }}
                >
                  <option value="">— select —</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="dataset-select">Dataset Version</FieldLabel>
                <Select
                  id="dataset-select"
                  value={form.datasetVersionId}
                  onChange={(e) => setField('datasetVersionId', e.target.value)}
                  disabled={!form.projectId || datasets.length === 0}
                >
                  <option value="">— select —</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.latest_version_id || d.id}>
                      {d.name}{!d.latest_version_id ? ' (no versions)' : ''}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="strategy-select">Sampling Strategy</FieldLabel>
                <Select
                  id="strategy-select"
                  value={form.strategy}
                  onChange={(e) => setField('strategy', e.target.value)}
                >
                  <option value="uncertainty">Uncertainty — random scoring (no model needed)</option>
                  <option value="diverse">Diversity — embedding-based spread</option>
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="k-input">Samples to Select (k)</FieldLabel>
                <Input
                  id="k-input"
                  type="number"
                  min={1}
                  max={500}
                  value={form.k}
                  onChange={(e) => setField('k', parseInt(e.target.value) || 20)}
                />
              </div>
            </div>

            <div className="border border-[var(--hud-border-subtle)] bg-[var(--hud-inset)] px-3 py-2 text-[0.6875rem] font-mono text-[var(--hud-text-muted)] space-y-1">
              <div><span className="text-[var(--hud-accent)]">uncertainty</span> — selects samples scored by random confidence proxy (use when no model is trained yet)</div>
              <div><span className="text-[var(--hud-accent)]">diverse</span> — selects samples spread across embedding space to maximise coverage</div>
            </div>
          </div>
        </div>

        {error && <Alert variant="error" className="mt-3">{error}</Alert>}

        <div className="pt-3">
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner size={12} />
                Selecting samples…
              </span>
            ) : (
              'Run Active Learning'
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
