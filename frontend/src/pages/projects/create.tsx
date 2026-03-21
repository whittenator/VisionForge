import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import ErrorState from '@/components/common/ErrorState';
import { apiPost } from '@/services/api';

interface Project {
  id: string;
  name: string;
  description?: string;
}

export default function ProjectsCreate() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [created, setCreated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) {
      setError('Project name is required');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const project = await apiPost<Project>('/api/projects', {
        name,
        description: description || undefined,
      });
      setCreated(`Created project ${name}`);
      setTimeout(() => navigate(`/projects/${project.id}`), 400);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <div className="label-overline mb-0.5">// Projects / New</div>
        <h1>New Project</h1>
      </div>

      {/* Form */}
      <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
        <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
          <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
          <span className="label-overline">Configuration</span>
        </div>
        <form onSubmit={onSubmit} className="p-4 space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="proj-name" className="label-overline block">
              Project Name <span className="text-[var(--hud-danger-text)]">*</span>
            </label>
            <Input
              id="proj-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-project"
              disabled={loading}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="proj-desc" className="label-overline block">
              Description <span className="text-[var(--hud-text-muted)]">(optional)</span>
            </label>
            <Input
              id="proj-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of project scope"
              disabled={loading}
            />
          </div>

          {error && <ErrorState title="Error" description={error} />}
          {created && <Alert variant="success">{created}</Alert>}

          <div className="flex items-center gap-2 pt-1">
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating…' : 'Create Project'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => navigate('/projects')}
              disabled={loading}
            >
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
