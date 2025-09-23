import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Link } from 'react-router-dom';
import { apiGet } from '@/services/api';

interface Artifact {
  id: string;
  type: string;
  version: number;
  createdAt: string;
}

export default function ArtifactsIndex() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Artifact[]>('/api/artifacts/models')
      .then(setArtifacts)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-semibold">Artifacts</h2>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? <p>Loading...</p> : artifacts.length === 0 ? <p>No artifacts yet.</p> : artifacts.map((a) => (
          <Card key={a.id}>
            <CardHeader><CardTitle>Model v{a.version}</CardTitle></CardHeader>
            <CardContent>
              <Badge className="mr-2">{a.type}</Badge>
              <Link className="text-blue-700 underline" to={`/artifacts/export/${a.id}`}>Export</Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
