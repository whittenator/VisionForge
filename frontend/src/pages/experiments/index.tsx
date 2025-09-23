import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import { apiGet } from '@/services/api';

interface Run {
  id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  createdAt: string;
  // add more fields as needed
}

export default function ExperimentsIndex() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Run[]>('/api/experiments/runs')
      .then(setRuns)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Experiments</h2>
        <Button as-child>
          <Link to="/experiments/new">New Training Run</Link>
        </Button>
      </div>
      <div className="mt-4 space-y-3">
        {loading ? <p>Loading...</p> : runs.length === 0 ? <p>No runs yet.</p> : runs.map((r) => (
          <Card key={r.id}>
            <CardHeader><CardTitle>Run {r.id}</CardTitle></CardHeader>
            <CardContent>
              <Badge variant={r.status === 'succeeded' ? 'success' : r.status === 'running' ? 'warning' : r.status === 'failed' ? 'danger' : 'default'}>
                {r.status}
              </Badge>
              <Link className="ml-4 text-blue-700 underline" to={`/experiments/runs/${r.id}`}>View Details</Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
