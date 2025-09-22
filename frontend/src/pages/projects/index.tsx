import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';

export default function ProjectsIndex() {
  const [loading] = useState(false);
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([
    { id: 'p1', name: 'Sample Project' },
  ]);

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Projects</h2>
        <Button as-child="true">
          {/* @ts-expect-error allow as-child semantics via attribute only */}
          <Link to="/projects/create">New Project</Link>
        </Button>
      </div>
      {loading ? (
        <div className="mt-4"><Loading label="Loading projects" /></div>
      ) : projects.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="No projects" description="Create your first project to begin.">
            <Button as-child="true">
              {/* @ts-expect-error allow as-child semantics via attribute only */}
              <Link to="/projects/create">New Project</Link>
            </Button>
          </EmptyState>
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Card key={p.id}>
              <CardHeader>
                <CardTitle>{p.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <Link className="text-blue-700 underline" to={`/projects/${p.id}`}>Open dashboard</Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
