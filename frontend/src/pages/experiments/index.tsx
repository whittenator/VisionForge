import React, { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

type Run = { id: string; name: string; status: 'queued' | 'running' | 'succeeded' };

export default function ExperimentsIndex() {
  const [runs, setRuns] = useState<Run[]>([]);

  function enqueue() {
    const id = `r_${Date.now()}`;
    setRuns((rs) => [...rs, { id, name: `Run ${rs.length + 1}`, status: 'queued' }]);
    setTimeout(() => setRuns((rs) => rs.map(r => r.id === id ? { ...r, status: 'running' } : r)), 500);
    setTimeout(() => setRuns((rs) => rs.map(r => r.id === id ? { ...r, status: 'succeeded' } : r)), 1200);
  }

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Experiments</h2>
        <Button onClick={enqueue}>New Training Run</Button>
      </div>
      <div className="mt-4 space-y-3">
        {runs.map((r) => (
          <Card key={r.id}>
            <CardHeader><CardTitle>{r.name}</CardTitle></CardHeader>
            <CardContent>
              <Badge variant={r.status === 'succeeded' ? 'success' : r.status === 'running' ? 'warning' : 'default'}>
                {r.status}
              </Badge>
            </CardContent>
          </Card>
        ))}
        {runs.length === 0 && <p className="text-sm text-gray-600">No runs yet.</p>}
      </div>
    </AppShell>
  );
}
