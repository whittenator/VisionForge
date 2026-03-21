import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import { apiGet } from '@/services/api';

interface Project {
  id: string;
  name: string;
  description?: string;
}

export default function ProjectsIndex() {
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    apiGet<Project[]>('/api/projects')
      .then(setProjects)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Projects</div>
          <h1>Projects</h1>
        </div>
        <Button as-child="true">
          {/* @ts-expect-error allow as-child semantics via attribute only */}
          <Link to="/projects/create">+ New Project</Link>
        </Button>
      </div>

      {loading ? (
        <div className="py-6"><Loading label="Loading projects…" /></div>
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects"
          description="Create your first project to begin managing datasets and training runs."
        >
          <Button as-child="true">
            {/* @ts-expect-error allow as-child semantics via attribute only */}
            <Link to="/projects/create">+ New Project</Link>
          </Button>
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-px sm:grid-cols-2 lg:grid-cols-3 bg-[var(--hud-border-default)]">
          {projects.map((p) => (
            <div
              key={p.id}
              className="bg-[var(--hud-surface)] p-4 flex flex-col gap-2 hover:bg-[var(--hud-elevated)] transition-colors group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="text-[0.625rem] font-mono text-[var(--hud-text-muted)] tracking-widest uppercase">
                  PROJECT
                </div>
              </div>
              <div className="font-semibold text-sm text-[var(--hud-text-primary)] tracking-wide">
                {p.name}
              </div>
              {p.description && (
                <p className="text-xs text-[var(--hud-text-muted)] leading-relaxed line-clamp-2">
                  {p.description}
                </p>
              )}
              <div className="mt-auto pt-2 border-t border-[var(--hud-border-subtle)]">
                <Link
                  to={`/projects/${p.id}`}
                  className="text-xs font-mono text-[var(--hud-accent)] hover:text-[var(--hud-accent-hover)] tracking-wide transition-colors"
                >
                  OPEN DASHBOARD →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
