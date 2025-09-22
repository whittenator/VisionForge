import React from 'react';
import { Link, useParams } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';

export default function ProjectDashboard() {
  const { projectId } = useParams();
  return (
    <AppShell>
      <h2 className="text-xl font-semibold">Project {projectId}</h2>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Datasets</CardTitle></CardHeader>
          <CardContent><div className="space-x-3">
            <Link className="text-blue-700 underline" to="/datasets/upload">Upload</Link>
            <Link className="text-blue-700 underline" to="/datasets/version">Snapshot</Link>
          </div></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Experiments</CardTitle></CardHeader>
          <CardContent><div className="space-x-3">
            <Link className="text-blue-700 underline" to="/experiments/new">New Run</Link>
            <Link className="text-blue-700 underline" to="/experiments">View Runs</Link>
          </div></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Artifacts</CardTitle></CardHeader>
          <CardContent>
          <Link className="text-blue-700 underline" to="/artifacts">Registry</Link>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
