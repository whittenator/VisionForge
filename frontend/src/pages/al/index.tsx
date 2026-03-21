import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiPost } from '@/services/api';

interface ALRun {
  id: string;
  project_id: string;
  strategy: string;
  created_at: string;
  params_json?: string;
  item_count?: number;
}

export default function ALIndex() {
  const [runs, setRuns] = useState<ALRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<any[]>([]);
  const [form, setForm] = useState({ projectId: '', strategy: 'uncertainty', k: 20, datasetId: '' });
  const [launching, setLaunching] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ALRun[]>('/api/al/runs').then(setRuns).catch(() => setRuns([])).finally(() => setLoading(false));
    apiGet<any[]>('/api/projects').then(setProjects).catch(() => {});
  }, []);

  async function launch() {
    if (!form.projectId) { setMsg('Select a project'); return; }
    setLaunching(true);
    setMsg(null);
    try {
      const result = await apiPost<ALRun>('/api/al/select', {
        project_id: form.projectId,
        strategy: form.strategy,
        k: form.k,
        dataset_id: form.datasetId || undefined,
      });
      setRuns(prev => [result, ...prev]);
      setMsg(`AL run created with ${form.k} samples selected`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Failed to launch AL run');
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Active Learning</h1>
      <p className="text-sm text-muted-foreground">
        Automatically select the most informative samples to annotate next, using uncertainty or diversity sampling.
      </p>

      {/* Launch form */}
      <Card>
        <CardHeader><CardTitle>New AL Selection</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Project</label>
              <select
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                value={form.projectId}
                onChange={e => setForm(f => ({ ...f, projectId: e.target.value }))}
              >
                <option value="">— Select —</option>
                {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Strategy</label>
              <select
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                value={form.strategy}
                onChange={e => setForm(f => ({ ...f, strategy: e.target.value }))}
              >
                <option value="uncertainty">Uncertainty Sampling</option>
                <option value="diverse">Diversity Sampling</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Samples (k)</label>
              <input
                type="number" min={1} max={500} value={form.k}
                onChange={e => setForm(f => ({ ...f, k: parseInt(e.target.value) || 20 }))}
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
              />
            </div>
            <div className="flex items-end">
              <Button onClick={launch} disabled={launching} className="w-full">
                {launching ? <span className="flex items-center gap-2"><Spinner />Selecting…</span> : 'Select Samples'}
              </Button>
            </div>
          </div>
          {msg && (
            <p className={`mt-3 text-sm ${msg.includes('Failed') || msg.includes('Select') ? 'text-red-600' : 'text-green-700'}`}>
              {msg}
            </p>
          )}
          <div className="mt-3 text-xs text-muted-foreground">
            <strong>Uncertainty:</strong> Selects assets where the model is least confident (requires a trained model).{' '}
            <strong>Diversity:</strong> Selects assets that are most different from each other based on embeddings.
          </div>
        </CardContent>
      </Card>

      {/* Run list */}
      <Card>
        <CardHeader><CardTitle>AL Runs ({runs.length})</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No AL runs yet. Create one above.</p>
          ) : (
            <div className="space-y-2">
              {runs.map(run => {
                let params: any = {};
                try { params = JSON.parse(run.params_json || '{}'); } catch {}
                return (
                  <div key={run.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge>{run.strategy}</Badge>
                        <span className="text-sm font-medium">{params.k || '?'} samples</span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(run.created_at).toLocaleString()}
                      </div>
                    </div>
                    <Link to={`/al/${run.id}`}>
                      <Button variant="outline" size="sm">Review Items →</Button>
                    </Link>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
